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

Loads fixture data from an eval case directory and prints the system prompt
and user prompt for each case so you can paste them into any model.
Compare the model's response against expected.json to verify correctness.

Usage:
    # Print prompts for all cases under a fixtures directory
    uv run --project tools/skill-evals skill-eval \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/

    # Print prompt for a single case
    uv run --project tools/skill-evals skill-eval \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/case-1-clear-duplicate
"""

from __future__ import annotations

import argparse
import json
import re
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
        description="Print eval prompts for skill cases. Paste into any model and compare against expected.json."
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
    args = parser.parse_args(argv)

    cases = find_cases(args.path)
    if not cases:
        print(f"No eval cases found under {args.path}", file=sys.stderr)
        return 1

    # Cache loaded step configs so we don't re-read prompts for every case in
    # the same fixtures dir (common when running a whole skill at once).
    _step_config_cache: dict[Path, tuple[str, str]] = {}

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
        print(f"{'=' * 60}")
        print(f"CASE: {step_label}/{case_dir.name}")
        print(f"{'=' * 60}")
        if not args.quiet:
            print("--- SYSTEM PROMPT ---")
            print(system_prompt)
            print("--- USER PROMPT ---")
            print(user_prompt)
        print("--- EXPECTED ---")
        print(json.dumps(expected, indent=2))
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
