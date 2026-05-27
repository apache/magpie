# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Skill eval runner.

Two modes:

1. **Print mode (default)** — emit the system prompt, user prompt, and
   expected JSON for each case. The operator (or the agent making the
   change, in self-eval mode) pastes the prompts into the model under
   test and diffs the response against expected.json manually.

2. **`--cli` mode** — pipe ``<system_prompt>\\n\\n<user_prompt>`` on stdin
   to the configured shell command, capture stdout, extract the JSON
   the model produced, and compare against expected.json automatically.
   Reports PASS / FAIL / MANUAL per case and exits non-zero on any FAIL.
   MANUAL is reserved for "structural" expected.json files (top-level
   ``has_*`` flags or ``mention_*`` lists) where automatic comparison
   is not meaningful; those still print prompts for manual review.

Usage:
    # Print prompts for all cases under a fixtures directory
    uv run --project tools/skill-evals skill-eval \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/

    # Print prompt for a single case
    uv run --project tools/skill-evals skill-eval \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/case-1-clear-duplicate

    # Automated comparison against a CLI (Claude Code shown; any LLM CLI
    # that reads a prompt on stdin and writes the response to stdout works)
    uv run --project tools/skill-evals skill-eval --cli "claude -p" \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

# Available slots: {corpus}, {roster}, {report}.
# Literal braces in a custom user-prompt-template.md that are NOT slots
# must be doubled ({{ and }}) so Python's str.format() leaves them intact.
USER_PROMPT_TEMPLATE = """\
## Existing open trackers (corpus)

{corpus}

## Reporter roster (existing trackers mapped to reporter email)

{roster}

## Incoming report

{report}

Apply the semantic sweep and reporter-identity check. Return JSON only.
"""


def build_corpus_text(corpus: list[dict]) -> str:
    lines = []
    for item in corpus:
        lines.append(f"#{item['number']} | {item['title']!r}")
        lines.append(f"Body (first 300 chars): {item['body']}")
        lines.append("")
    return "\n".join(lines)


def build_roster_text(roster: dict[str, str]) -> str:
    if not roster:
        return "(none)"
    return "\n".join(f"#{num}: {email}" for num, email in roster.items())


def find_repo_root(start: Path) -> Path:
    """Walk up the directory tree until a .git directory is found."""
    p = start.resolve()
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    raise RuntimeError(f"Could not find repo root (.git) from {start}")


def extract_skill_section(skill_md_path: Path, heading: str) -> str:
    """Return the section of a SKILL.md that begins with *heading*.

    Extraction ends at the next heading of the same or higher level, or at
    the end of the file.  Raises ValueError if the heading is not found.
    """
    text = skill_md_path.read_text()
    lines = text.split("\n")
    heading_stripped = heading.rstrip()
    m = re.match(r"^(#{1,6}) ", heading_stripped)
    if not m:
        raise ValueError(f"Heading {heading!r} does not look like a Markdown heading")
    heading_level = len(m.group(1))

    start = next(
        (i for i, line in enumerate(lines) if line.rstrip() == heading_stripped),
        None,
    )
    if start is None:
        raise ValueError(f"Heading {heading!r} not found in {skill_md_path}")

    end = len(lines)
    in_fence = False
    for i in range(start + 1, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        if in_fence:
            continue
        hm = re.match(r"^(#{1,6}) ", lines[i])
        if hm and len(hm.group(1)) <= heading_level:
            end = i
            break

    return "\n".join(lines[start:end]).rstrip()


def load_step_config(fixtures_dir: Path) -> tuple[str, str]:
    """Return (system_prompt, user_prompt_template) for the given fixtures dir.

    Resolution order:
    1. ``step-config.json`` — extracts the step section live from the skill's
       SKILL.md, then appends ``output-spec.md`` if present.  This is the
       preferred path: tests automatically exercise the current skill text.
    2. ``system-prompt.md`` — a manually maintained prompt used by triage steps.

    Raises FileNotFoundError if neither file is present.
    """
    user_tmpl_path = fixtures_dir / "user-prompt-template.md"
    user_prompt_template = user_tmpl_path.read_text() if user_tmpl_path.exists() else USER_PROMPT_TEMPLATE

    # 1. step-config.json → live extraction from SKILL.md
    config_path = fixtures_dir / "step-config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        repo_root = find_repo_root(fixtures_dir)
        skill_md_path = repo_root / config["skill_md"]
        section = extract_skill_section(skill_md_path, config["step_heading"])
        output_spec_path = fixtures_dir / "output-spec.md"
        if output_spec_path.exists():
            section += "\n\n" + output_spec_path.read_text()
        return section, user_prompt_template

    # 2. system-prompt.md → manually maintained (triage steps)
    sys_prompt_path = fixtures_dir / "system-prompt.md"
    if sys_prompt_path.exists():
        return sys_prompt_path.read_text(), user_prompt_template

    raise FileNotFoundError(
        f"{fixtures_dir} has neither step-config.json nor system-prompt.md. "
        "Add a step-config.json pointing at the relevant SKILL.md section."
    )


# ---------------------------------------------------------------------------
# Case loading
# ---------------------------------------------------------------------------


def load_case(case_dir: Path) -> tuple[list[dict], dict, str, dict]:
    """Return (corpus, roster, report_text, expected).

    ``corpus.json`` is optional — steps that do not need a tracker corpus
    (e.g. Step 3 classification) simply omit it and get an empty list.
    """
    fixtures_dir = case_dir.parent
    corpus_path = fixtures_dir / "corpus.json"
    roster_path = fixtures_dir / "reporter-roster.json"

    corpus = json.loads(corpus_path.read_text()) if corpus_path.exists() else []
    roster = json.loads(roster_path.read_text()) if roster_path.exists() else {}
    report = (case_dir / "report.md").read_text()
    expected = json.loads((case_dir / "expected.json").read_text())
    return corpus, roster, report, expected


def load_case_tags(case_dir: Path) -> set[str]:
    """Return optional runner-selection tags for a case.

    Tags live in ``case-meta.json`` so expected.json stays focused on the
    behavioral assertion.  Unknown metadata keys are ignored.
    """
    meta_path = case_dir / "case-meta.json"
    if not meta_path.exists():
        return set()
    meta = json.loads(meta_path.read_text())
    tags = meta.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError(f"{meta_path} must contain a string-list 'tags' field")
    return set(tags)


# ---------------------------------------------------------------------------
# Automated comparison (--cli mode)
# ---------------------------------------------------------------------------


def is_structural_expected(expected: dict) -> bool:
    """Return True if expected.json describes prose properties, not exact output.

    Composition steps (e.g. compose-comment, compose-verdict) assert structural
    properties of the model's prose via boolean ``has_*`` flags and membership
    lists like ``mention_handles``.  Those cannot be JSON-equality-compared
    against a model's actual prose output, so --cli mode falls back to manual
    review for them.
    """
    if not isinstance(expected, dict):
        return False
    return any(key.startswith(("has_", "mention_")) for key in expected)


def extract_json_from_output(text: str) -> tuple[object | None, str | None]:
    """Return (parsed_json, error) extracted from a model's stdout.

    Tries three strategies in order:
      1. The whole output is valid JSON.
      2. The output contains a ```json ... ``` fenced block.
      3. The output contains a balanced ``{...}`` (or ``[...]``) block — the
         longest such block is tried.

    Returns ``(value, None)`` on success or ``(None, error_message)`` if no
    JSON could be extracted.
    """
    stripped = text.strip()
    if stripped:
        try:
            return json.loads(stripped), None
        except json.JSONDecodeError:
            pass

    fence = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1).strip()), None
        except json.JSONDecodeError:
            pass

    candidate = _find_largest_brace_block(text)
    if candidate is not None:
        try:
            return json.loads(candidate), None
        except json.JSONDecodeError:
            pass

    return None, "no JSON object or array found in model output"


def _find_largest_brace_block(text: str) -> str | None:
    """Return the largest balanced ``{...}`` or ``[...]`` substring, or None."""
    best: str | None = None
    for opener, closer in (("{", "}"), ("[", "]")):
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == opener:
                if depth == 0:
                    start = i
                depth += 1
            elif ch == closer and depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidate = text[start : i + 1]
                    if best is None or len(candidate) > len(best):
                        best = candidate
                    start = -1
    return best


def compare_outputs(actual: object, expected: object) -> tuple[bool, str]:
    """Return (passed, diff_text). Diff is empty when passed=True."""
    if actual == expected:
        return True, ""
    return False, _format_diff(actual, expected)


def _format_diff(actual: object, expected: object) -> str:
    actual_text = json.dumps(actual, indent=2, sort_keys=True)
    expected_text = json.dumps(expected, indent=2, sort_keys=True)
    a_lines = actual_text.splitlines()
    e_lines = expected_text.splitlines()
    lines = ["--- expected", "+++ actual"]
    for line in e_lines:
        if line not in a_lines:
            lines.append(f"- {line}")
    for line in a_lines:
        if line not in e_lines:
            lines.append(f"+ {line}")
    return "\n".join(lines)


def run_cli(cli: str, prompt: str, timeout: int = 120) -> tuple[str, str, int]:
    """Run ``cli`` (shell command) with ``prompt`` on stdin. Return (stdout, stderr, rc).

    The command is run with ``shell=True`` so quoting and arguments work as a
    developer would type them at a shell prompt. The runner is a local
    developer tool — the operator supplies the command, so shell semantics are
    the ergonomic choice rather than a security concern.
    """
    proc = subprocess.run(
        cli,
        input=prompt,
        capture_output=True,
        text=True,
        shell=True,
        timeout=timeout,
        check=False,
    )
    return proc.stdout, proc.stderr, proc.returncode


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def find_cases(path: Path) -> list[tuple[Path, Path]]:
    """Return (case_dir, fixtures_dir) pairs under path.

    Handles three levels of granularity:
      - single case dir     (contains report.md)
      - fixtures dir        (contains case-* subdirs)
      - skill/step dir      (contains fixtures/ subdirs recursively)
    """
    if (path / "report.md").exists():
        return [(path, path.parent)]
    # Direct fixtures dir — all cases share the same fixtures dir.
    direct = sorted(p for p in path.iterdir() if p.is_dir() and (p / "report.md").exists())
    if direct:
        return [(p, path) for p in direct]
    # Recursive search — e.g. skill dir spanning multiple steps.
    # De-duplicate: skip any fixtures/ that is itself nested under another
    # fixtures/ already in the set (guards against accidental double-counting
    # if someone copies a case sub-tree that contains its own fixtures/).
    results = []
    seen_fixtures: set[Path] = set()
    for fixtures_dir in sorted(path.rglob("fixtures")):
        if not fixtures_dir.is_dir():
            continue
        if any(fixtures_dir.is_relative_to(f) for f in seen_fixtures):
            continue
        seen_fixtures.add(fixtures_dir)
        for case_dir in sorted(fixtures_dir.iterdir()):
            if case_dir.is_dir() and (case_dir / "report.md").exists():
                results.append((case_dir, fixtures_dir))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run skill eval cases. Default mode prints prompts for manual review. "
            "--cli mode pipes prompts through a shell command and auto-compares "
            "against expected.json."
        )
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a single case directory or a fixtures directory containing multiple cases.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress prompt content; print only case names and expected JSON.",
    )
    parser.add_argument(
        "--cli",
        type=str,
        default=None,
        help=(
            "Shell command that reads a prompt on stdin and writes the model "
            "response to stdout (e.g. 'claude -p'). When set, the runner sends "
            "<system_prompt>\\n\\n<user_prompt> to the command for each case, "
            "extracts JSON from stdout, and compares against expected.json. "
            "Exits non-zero on any FAIL."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout in seconds for each --cli invocation (default: 120).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="In --cli mode, also print the prompts and the model's raw stdout per case.",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help=(
            "Run only cases tagged in case-meta.json. May be passed multiple "
            "times; a case is included if it has all requested tags."
        ),
    )
    args = parser.parse_args(argv)

    cases = find_cases(args.path)
    if args.tag:
        requested_tags = set(args.tag)
        cases = [
            (case_dir, fixtures_dir)
            for case_dir, fixtures_dir in cases
            if requested_tags.issubset(load_case_tags(case_dir))
        ]
    if not cases:
        tag_suffix = f" matching tag(s): {', '.join(args.tag)}" if args.tag else ""
        print(f"No eval cases found under {args.path}{tag_suffix}", file=sys.stderr)
        return 1

    # Cache loaded step configs so we don't re-read prompts for every case in
    # the same fixtures dir (common when running a whole skill at once).
    _step_config_cache: dict[Path, tuple[str, str]] = {}

    passed = failed = manual = errored = 0

    for case_dir, fixtures_dir in cases:
        if fixtures_dir not in _step_config_cache:
            _step_config_cache[fixtures_dir] = load_step_config(fixtures_dir)
        system_prompt, user_prompt_template = _step_config_cache[fixtures_dir]

        corpus, roster, report, expected = load_case(case_dir)
        try:
            user_prompt = user_prompt_template.format(
                corpus=build_corpus_text(corpus),
                roster=build_roster_text(roster),
                report=report,
            )
        except (KeyError, ValueError) as exc:
            raise type(exc)(
                f"user-prompt-template.md in {fixtures_dir} has a format error: {exc}. "
                "Available slots: {{corpus}}, {{roster}}, {{report}}. "
                "Literal braces that are not slots must be doubled ({{ and }})."
            ) from exc
        step_label = fixtures_dir.parent.name
        case_label = f"{step_label}/{case_dir.name}"

        if args.cli is None:
            # Print mode (existing behaviour)
            print(f"{'=' * 60}")
            print(f"CASE: {case_label}")
            print(f"{'=' * 60}")
            if not args.quiet:
                print("--- SYSTEM PROMPT ---")
                print(system_prompt)
                print("--- USER PROMPT ---")
                print(user_prompt)
            print("--- EXPECTED ---")
            print(json.dumps(expected, indent=2))
            print()
            continue

        # --cli mode: run the configured command and auto-compare.
        if isinstance(expected, dict) and is_structural_expected(expected):
            print(f"MANUAL  {case_label} (structural expected.json — review actual output by hand)")
            if args.verbose:
                _print_prompts_and_run(args, system_prompt, user_prompt)
            manual += 1
            continue

        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        try:
            stdout, stderr, rc = run_cli(args.cli, full_prompt, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f"ERROR   {case_label} (CLI timed out after {args.timeout}s)")
            errored += 1
            continue
        except OSError as exc:
            print(f"ERROR   {case_label} (CLI invocation failed: {exc})")
            errored += 1
            continue

        if rc != 0:
            print(f"ERROR   {case_label} (CLI exited {rc}; stderr: {stderr.strip()[:200]})")
            errored += 1
            if args.verbose:
                print("--- STDOUT ---")
                print(stdout)
            continue

        actual, parse_err = extract_json_from_output(stdout)
        if parse_err is not None:
            print(f"ERROR   {case_label} ({parse_err})")
            errored += 1
            if args.verbose:
                print("--- STDOUT ---")
                print(stdout)
            continue

        ok, diff = compare_outputs(actual, expected)
        if ok:
            print(f"PASS    {case_label}")
            passed += 1
        else:
            print(f"FAIL    {case_label}")
            print(diff)
            failed += 1

        if args.verbose:
            print("--- SYSTEM PROMPT ---")
            print(system_prompt)
            print("--- USER PROMPT ---")
            print(user_prompt)
            print("--- STDOUT ---")
            print(stdout)
            print()

    if args.cli is not None:
        total = passed + failed + manual + errored
        print()
        print(f"{'=' * 60}")
        print(f"Ran {total} cases: {passed} passed, {failed} failed, {manual} manual, {errored} errored")
        print(f"{'=' * 60}")
        if failed or errored:
            return 1

    return 0


def _print_prompts_and_run(args: argparse.Namespace, system_prompt: str, user_prompt: str) -> None:
    """Verbose helper for MANUAL-mode cases: show what would have been sent."""
    print("--- SYSTEM PROMPT ---")
    print(system_prompt)
    print("--- USER PROMPT ---")
    print(user_prompt)


if __name__ == "__main__":
    sys.exit(main())
