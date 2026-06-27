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
   "Structural" expected.json files (top-level ``has_*`` flags or
   ``mention_*`` lists) assert properties of the model's prose rather than
   exact field values. When the fixtures dir provides an ``assertions.json``
   mapping each such key to a predicate (``regex`` / ``contains`` /
   ``contains_all`` / ``empty`` / ``non_empty`` / ``field_true`` run locally;
   ``judge`` piped to the grader CLI), those cases are graded automatically.
   Any predicate may carry ``"negate": true`` to assert the absence of a
   match. A structural case with no ``assertions.json`` falls back to MANUAL
   and prints prompts for manual review.

   By default, free-text fields (rationale, reason, drop_reason,
   blockers, etc.) are graded by piping a short rubric prompt to a
   cheap judge model (``claude -p --model haiku`` by default) and
   parsing ``{"match": bool, "reason": str}``. Decision fields
   (booleans, enums, counts, ordering, IDs) are still compared
   exactly. Override the grader command with ``--grader-cli``, or pass
   ``--exact`` to disable grading and require verbatim equality on
   every field. The set of prose fields defaults to a built-in list
   and can be overridden per fixtures dir via ``grading-schema.json``.
   No caching: every prose field is sent to the grader on every run.

Usage:
    # Print prompts for all cases under a fixtures directory
    uv run --project tools/skill-evals skill-eval \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/

    # Print prompt for a single case
    uv run --project tools/skill-evals skill-eval \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/case-1-clear-duplicate

    # Automated comparison against a CLI. Decision fields are graded
    # exact; prose fields go to the default grader (claude -p --model haiku).
    uv run --project tools/skill-evals skill-eval --cli "claude -p" \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/

    # Override the grader, e.g. to use a different cheap model.
    uv run --project tools/skill-evals skill-eval \\
        --cli "claude -p" \\
        --grader-cli "llm -m gpt-4o-mini" \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/

    # Disable the grader and require verbatim JSON equality on every field.
    uv run --project tools/skill-evals skill-eval --cli "claude -p" --exact \\
        evals/security-issue-import/step-2a-semantic-sweep/fixtures/
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
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


# ---------------------------------------------------------------------------
# Field-aware grading (--grader-cli mode)
# ---------------------------------------------------------------------------

# Default grader shell command. Used when --cli is set and --exact is not.
# Haiku is the cheapest Claude model; the rubric is small so cost is minimal.
DEFAULT_GRADER_CLI: str = "claude -p --model haiku"


# Keys whose values are treated as prose by default. The runner sends these
# to the grader CLI for a soft "does the candidate support the same
# conclusion?" judgement instead of requiring verbatim string equality.
# A per-fixtures-dir ``grading-schema.json`` can replace this list.
DEFAULT_PROSE_FIELDS: frozenset[str] = frozenset(
    {
        "rationale",
        "reason",
        "reasons",
        "drop_reason",
        "blockers",
        "notes",
        "summary",
        "explanation",
        "details",
        "description",
    }
)


GRADER_RUBRIC = """\
You are grading one field of a model's structured answer against a reference answer.

Field path: {field_path}

Expected value:
{expected_value}

Candidate value:
{candidate_value}

Does the candidate value support the same conclusion as the expected value? Ignore wording differences and reorderings. Reply with one line of JSON only, no prose: {{"match": true, "reason": "<one-line explanation>"}} or {{"match": false, "reason": "<one-line explanation>"}}.
"""


BATCH_GRADER_RUBRIC = """\
You are grading a model's structured answer against a reference answer, field by field.

For each (Field, Expected, Candidate) triple below, decide whether the candidate value supports the same conclusion as the expected value. Ignore wording differences and reorderings.

{fields_block}

Reply with one line of JSON only, no prose. The JSON is an object mapping each field path string to {{"match": true|false, "reason": "<one-line explanation>"}}. Include every field listed above. Example:
{{"$.foo": {{"match": true, "reason": "same conclusion"}}, "$.bar": {{"match": false, "reason": "different verdict"}}}}
"""


def load_grading_schema(fixtures_dir: Path) -> set[str]:
    """Return the set of prose field names for cases in this fixtures dir.

    Reads ``fixtures_dir/grading-schema.json`` when present. The file may
    set ``prose_fields`` to a string list that *replaces* the default set
    (use ``["rationale", "reason", ...]`` to be explicit, or ``[]`` to
    grade everything by exact match).

    Falls back to :data:`DEFAULT_PROSE_FIELDS` when no schema file exists.
    """
    path = fixtures_dir / "grading-schema.json"
    if not path.exists():
        return set(DEFAULT_PROSE_FIELDS)
    data = json.loads(path.read_text())
    fields = data.get("prose_fields")
    if fields is None:
        return set(DEFAULT_PROSE_FIELDS)
    if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
        raise ValueError(f"{path} must contain a string-list 'prose_fields' field")
    return set(fields)


def _render_field_value(value: object) -> str:
    """Render an expected/candidate field value for the grader prompt."""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def grade_prose_field(
    field_path: str,
    expected_value: object,
    actual_value: object,
    grader_cli: str,
    timeout: int,
) -> tuple[bool, str]:
    """Ask the grader CLI whether the candidate value supports the same conclusion.

    Returns ``(match, note)``. ``note`` is empty on match and a one-line
    summary on mismatch (or grader failure).
    """
    if expected_value == actual_value:
        return True, ""
    prompt = GRADER_RUBRIC.format(
        field_path=field_path,
        expected_value=_render_field_value(expected_value),
        candidate_value=_render_field_value(actual_value),
    )
    try:
        stdout, stderr, rc = run_cli(grader_cli, prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"{field_path}: grader CLI timed out after {timeout}s"
    except OSError as exc:
        return False, f"{field_path}: grader CLI invocation failed ({exc})"
    if rc != 0:
        return False, f"{field_path}: grader CLI exited {rc} ({stderr.strip()[:200]})"
    verdict, err = extract_json_from_output(stdout)
    if err is not None or not isinstance(verdict, dict) or "match" not in verdict:
        return False, f"{field_path}: grader returned unusable output ({err or 'missing match key'})"
    match = bool(verdict.get("match"))
    reason = str(verdict.get("reason", "")).strip()
    if match:
        return True, ""
    return False, f"{field_path}: grader says NO ({reason or 'no reason given'})"


def collect_diffs(
    actual: object,
    expected: object,
    *,
    prose_fields: set[str],
    path: str = "$",
) -> tuple[list[str], list[tuple[str, object, object]]]:
    """Walk both trees in parallel; return (decision_msgs, prose_pairs).

    ``decision_msgs`` lists structural/decision-field mismatches (type, key
    set, list length, scalar inequality on non-prose keys). These cannot
    be resolved by the grader. ``prose_pairs`` lists
    ``(field_path, expected_value, actual_value)`` for prose-keyed
    mismatches that the grader should judge. Equal values are omitted from
    both lists.
    """
    if type(actual) is not type(expected):
        return [
            f"{path}: type mismatch (actual={type(actual).__name__}, expected={type(expected).__name__})"
        ], []

    if isinstance(expected, dict):
        actual_dict = actual  # type: ignore[assignment]
        # Only assert on the intersection of keys. Keys in expected that the
        # model didn't emit are skipped (not failed), and keys in actual that
        # expected doesn't declare are ignored. expected.json describes what
        # the model's answer SHOULD say where it speaks, not what it must
        # include.
        decision_msgs: list[str] = []
        prose_pairs: list[tuple[str, object, object]] = []
        for key in expected:
            if key not in actual_dict:
                continue
            child_path = f"{path}.{key}" if path else key
            if key in prose_fields:
                if expected[key] != actual_dict[key]:
                    prose_pairs.append((child_path, expected[key], actual_dict[key]))
            else:
                sub_d, sub_p = collect_diffs(
                    actual_dict[key],
                    expected[key],
                    prose_fields=prose_fields,
                    path=child_path,
                )
                decision_msgs.extend(sub_d)
                prose_pairs.extend(sub_p)
        return decision_msgs, prose_pairs

    if isinstance(expected, list):
        actual_list = actual  # type: ignore[assignment]
        if len(actual_list) != len(expected):
            return [f"{path}: length mismatch (actual={len(actual_list)}, expected={len(expected)})"], []
        decision_msgs = []
        prose_pairs = []
        for i, (a_item, e_item) in enumerate(zip(actual_list, expected, strict=False)):
            sub_d, sub_p = collect_diffs(
                a_item,
                e_item,
                prose_fields=prose_fields,
                path=f"{path}[{i}]",
            )
            decision_msgs.extend(sub_d)
            prose_pairs.extend(sub_p)
        return decision_msgs, prose_pairs

    if actual == expected:
        return [], []
    return [f"{path}: expected={expected!r}, actual={actual!r}"], []


def _format_batch_fields_block(pairs: list[tuple[str, object, object]]) -> str:
    chunks = []
    for path, expected, actual in pairs:
        chunks.append(
            f"Field: {path}\nExpected:\n{_render_field_value(expected)}\nCandidate:\n{_render_field_value(actual)}"
        )
    return "\n\n".join(chunks)


def batch_grade_prose_fields(
    pairs: list[tuple[str, object, object]],
    grader_cli: str,
    timeout: int,
) -> dict[str, tuple[bool, str]]:
    """Send one rubric prompt covering every pair; return path -> (match, note).

    Returns an empty dict when ``pairs`` is empty (no grader call). On grader
    failure (timeout, OSError, non-zero exit, unparsable output, missing
    path in the verdict), every pair without a clean verdict is returned as
    ``(False, <one-line explanation>)``.
    """
    if not pairs:
        return {}
    prompt = BATCH_GRADER_RUBRIC.format(fields_block=_format_batch_fields_block(pairs))
    try:
        stdout, stderr, rc = run_cli(grader_cli, prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {p: (False, f"grader CLI timed out after {timeout}s") for p, _, _ in pairs}
    except OSError as exc:
        return {p: (False, f"grader CLI invocation failed ({exc})") for p, _, _ in pairs}
    if rc != 0:
        return {p: (False, f"grader CLI exited {rc} ({stderr.strip()[:200]})") for p, _, _ in pairs}
    verdict, err = extract_json_from_output(stdout)
    if err is not None or not isinstance(verdict, dict):
        return {p: (False, f"grader returned unusable output ({err or 'not a dict'})") for p, _, _ in pairs}
    result: dict[str, tuple[bool, str]] = {}
    for path, _, _ in pairs:
        entry = verdict.get(path)
        if not isinstance(entry, dict) or "match" not in entry:
            result[path] = (False, f"grader did not return a verdict for {path}")
            continue
        match = bool(entry.get("match"))
        reason = str(entry.get("reason", "")).strip()
        if match:
            result[path] = (True, "")
        else:
            result[path] = (False, f"grader says NO ({reason or 'no reason given'})")
    return result


def compare_with_grader(
    actual: object,
    expected: object,
    *,
    prose_fields: set[str],
    grader_cli: str,
    timeout: int,
) -> tuple[bool, list[str]]:
    """Field-aware comparison: decision keys exact, prose keys judged by grader.

    Walks both trees once to separate decision-field diffs from prose-field
    diffs, then makes a single batched grader call covering every prose
    mismatch. If decision fields already fail the comparison, the grader
    is skipped entirely (one fewer CLI call per failing case).

    Returns ``(ok, messages)``; ``messages`` is empty when ok and otherwise
    lists one note per failing field.
    """
    decision_msgs, prose_pairs = collect_diffs(actual, expected, prose_fields=prose_fields)
    if decision_msgs:
        # Case already fails on a decision field; no need to call the grader.
        return False, decision_msgs
    if not prose_pairs:
        return True, []
    grades = batch_grade_prose_fields(prose_pairs, grader_cli, timeout)
    ok = True
    msgs: list[str] = []
    for path, _, _ in prose_pairs:
        match, note = grades.get(path, (False, f"{path}: no verdict returned by grader"))
        if not match:
            ok = False
            # `note` from batch_grade_prose_fields is already field-attributed
            # for missing entries; for grader verdicts it isn't, so prepend the
            # path for clarity in the output.
            if note.startswith(path):
                msgs.append(note)
            else:
                msgs.append(f"{path}: {note}")
    return ok, msgs


# ---------------------------------------------------------------------------
# Structural assertions (has_* / mention_* keys)
# ---------------------------------------------------------------------------

# Structural expected.json files assert *properties of the model's prose*
# (does the announce body contain the Download Page link? did the model flag
# the injection?) rather than exact field values. Each such property is named
# by a has_* / mention_* key and is evaluated by a predicate declared in the
# fixtures dir's assertions.json. Deterministic predicate types run locally —
# fast, free, and flake-free, which is exactly what you want for links,
# headers, and security properties. The judge type pipes a yes/no rubric to
# the grader CLI for the genuinely semantic properties that regex can't pin
# down.

_DETERMINISTIC_ASSERTION_TYPES: frozenset[str] = frozenset(
    {"regex", "contains", "contains_all", "empty", "non_empty", "field_true"}
)
_VALID_ASSERTION_TYPES: frozenset[str] = _DETERMINISTIC_ASSERTION_TYPES | {"judge"}


def load_assertions(fixtures_dir: Path) -> dict[str, dict]:
    """Return the structural-assertion specs for cases in this fixtures dir.

    Reads ``fixtures_dir/assertions.json`` when present: an object mapping
    each ``has_*`` / ``mention_*`` key to a predicate spec. Returns an empty
    dict when the file is absent — the runner then falls back to MANUAL for
    structural cases, preserving the prior behaviour.

    Raises ValueError if the file is malformed or names an unknown predicate
    type, so a typo fails loudly rather than silently skipping a check.
    """
    path = fixtures_dir / "assertions.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object mapping assertion keys to specs")
    for key, spec in data.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: assertion {key!r} must be an object")
        atype = spec.get("type")
        if atype not in _VALID_ASSERTION_TYPES:
            raise ValueError(
                f"{path}: assertion {key!r} has invalid type {atype!r}; "
                f"valid types: {sorted(_VALID_ASSERTION_TYPES)}"
            )
    return data


def _resolve_field(actual: object, field: str) -> tuple[object, bool]:
    """Return ``(value, present)`` for a dotted ``field`` path into ``actual``."""
    cur = actual
    for part in field.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None, False
    return cur, True


def _compile_flags(spec: dict) -> int:
    flags = 0
    mapping = {"i": re.IGNORECASE, "s": re.DOTALL, "m": re.MULTILINE}
    for ch in str(spec.get("flags", "")):
        flags |= mapping.get(ch, 0)
    return flags


def evaluate_deterministic_assertion(spec: dict, actual: object) -> tuple[bool | None, str]:
    """Evaluate a non-judge assertion. Return ``(holds, note)``.

    ``holds`` is True/False for whether the asserted property is present in
    the model output, or None on a spec/usage error (which the caller reports
    as a failure). ``note`` is a short explanation, empty on a clean result.

    Missing-field semantics: ``empty`` treats an absent field as empty (True);
    ``non_empty`` / ``field_true`` / the text predicates treat an absent field
    as not satisfied (False).

    A ``"negate": true`` key inverts the result, so a predicate can assert the
    *absence* of a pattern (e.g. ``has_no_passphrase_arg`` checks that the
    ``--passphrase`` token does not appear). Negation is applied only to a
    concrete True/False result; a spec/usage error (None) is passed through
    unchanged so the typo still fails loudly.
    """
    holds, note = _evaluate_deterministic_assertion_raw(spec, actual)
    if spec.get("negate") and holds is not None:
        holds = not holds
    return holds, note


def _evaluate_deterministic_assertion_raw(spec: dict, actual: object) -> tuple[bool | None, str]:
    """Evaluate the predicate before any ``negate`` inversion is applied."""
    atype = spec["type"]
    field = spec.get("field")
    if field is None:
        return None, f"type {atype!r} requires a 'field'"
    value, present = _resolve_field(actual, field)

    if atype == "empty":
        return (not present or value in ([], "", None, {})), ""
    if atype == "non_empty":
        return (present and value not in ([], "", None, {})), ""
    if atype == "field_true":
        return (present and value is True), ""

    # Text predicates need a string. Non-string values are JSON-serialised so
    # a list/number field can still be substring/regex-matched if a spec asks.
    if not present:
        return False, f"field {field!r} not present in output"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    ci = "i" in str(spec.get("flags", ""))

    if atype == "regex":
        pattern = spec.get("pattern")
        if pattern is None:
            return None, "type 'regex' requires a 'pattern'"
        return (re.search(pattern, text, _compile_flags(spec)) is not None), ""
    if atype == "contains":
        sub = spec.get("substring")
        if sub is None:
            return None, "type 'contains' requires a 'substring'"
        hay = text.lower() if ci else text
        needle = sub.lower() if ci else sub
        return (needle in hay), ""
    if atype == "contains_all":
        subs = spec.get("substrings")
        if not isinstance(subs, list) or not subs:
            return None, "type 'contains_all' requires a non-empty 'substrings' list"
        hay = text.lower() if ci else text
        missing = [s for s in subs if (s.lower() if ci else s) not in hay]
        return (not missing), (f"missing: {missing}" if missing else "")
    return None, f"unhandled assertion type {atype!r}"


JUDGE_ASSERTION_RUBRIC = """\
You are checking whether a model's output satisfies specific named properties.

Model output (JSON):
{output}

For each property below, decide strictly from the output whether the property holds.

{props_block}

Reply with one line of JSON only, no prose: an object mapping each property key to {{"holds": true|false, "reason": "<one-line explanation>"}}. Include every property key listed above. Example:
{{"has_foo": {{"holds": true, "reason": "output states X"}}, "mention_bar": {{"holds": false, "reason": "not mentioned"}}}}
"""


def _format_judge_props_block(specs: dict[str, dict]) -> str:
    chunks = []
    for key, spec in specs.items():
        rubric = spec.get("rubric", "")
        field = spec.get("field")
        scope = f" (focus on the {field!r} field)" if field else ""
        chunks.append(f"Property: {key}{scope}\nHolds when: {rubric}")
    return "\n\n".join(chunks)


def batch_judge_assertions(
    specs: dict[str, dict],
    actual: object,
    grader_cli: str,
    timeout: int,
) -> dict[str, tuple[bool | None, str]]:
    """Send one rubric covering every judge assertion; return key -> (holds, note).

    Empty ``specs`` makes no grader call. On any grader failure (timeout,
    OSError, non-zero exit, unparsable output, missing key in the verdict),
    the affected keys are returned with ``holds=None`` so the caller fails the
    assertion rather than silently passing it — important for the security
    cases this is used on.
    """
    if not specs:
        return {}
    prompt = JUDGE_ASSERTION_RUBRIC.format(
        output=json.dumps(actual, indent=2, ensure_ascii=False, sort_keys=True),
        props_block=_format_judge_props_block(specs),
    )
    try:
        stdout, stderr, rc = run_cli(grader_cli, prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        return dict.fromkeys(specs, (None, f"grader CLI timed out after {timeout}s"))
    except OSError as exc:
        return dict.fromkeys(specs, (None, f"grader CLI invocation failed ({exc})"))
    if rc != 0:
        return dict.fromkeys(specs, (None, f"grader CLI exited {rc} ({stderr.strip()[:200]})"))
    verdict, err = extract_json_from_output(stdout)
    if err is not None or not isinstance(verdict, dict):
        return dict.fromkeys(specs, (None, f"grader returned unusable output ({err or 'not a dict'})"))
    result: dict[str, tuple[bool | None, str]] = {}
    for key in specs:
        entry = verdict.get(key)
        if not isinstance(entry, dict) or "holds" not in entry:
            result[key] = (None, f"grader did not return a verdict for {key}")
            continue
        result[key] = (bool(entry.get("holds")), str(entry.get("reason", "")).strip())
    return result


def compare_structural(
    actual: object,
    expected: dict,
    assertions: dict[str, dict],
    *,
    prose_fields: set[str],
    grader_cli: str,
    exact: bool,
    grader_timeout: int,
) -> tuple[bool, list[str]]:
    """Grade a structural expected.json (``has_*`` / ``mention_*`` keys).

    Structural keys are evaluated by their ``assertions.json`` predicates;
    deterministic ones run locally and judge ones go to the grader in a single
    batched call. Any remaining (non-structural) keys are compared with the
    standard field-aware comparator — exact for decision fields, grader for
    prose, or pure exact when ``exact`` is set. Returns ``(ok, notes)`` with
    one note per failing field.
    """
    structural = {k: v for k, v in expected.items() if k.startswith(("has_", "mention_"))}
    remainder = {k: v for k, v in expected.items() if k not in structural}

    ok = True
    notes: list[str] = []

    if remainder:
        sub_ok, sub_notes = compare_with_grader(
            actual,
            remainder,
            prose_fields=set() if exact else prose_fields,
            grader_cli=grader_cli,
            timeout=grader_timeout,
        )
        if not sub_ok:
            ok = False
            notes.extend(sub_notes)

    judge_specs: dict[str, dict] = {}
    judge_expected: dict[str, bool] = {}
    for key, exp_val in structural.items():
        spec = assertions.get(key)
        if spec is None:
            ok = False
            notes.append(f"{key}: no assertion defined in assertions.json")
            continue
        if spec["type"] == "judge":
            judge_specs[key] = spec
            judge_expected[key] = bool(exp_val)
            continue
        holds, note = evaluate_deterministic_assertion(spec, actual)
        if holds is None:
            ok = False
            notes.append(f"{key}: {note}")
        elif holds != bool(exp_val):
            detail = f" ({note})" if note else ""
            notes.append(f"{key}: property={holds}, expected {bool(exp_val)}{detail}")
            ok = False

    if judge_specs:
        grades = batch_judge_assertions(judge_specs, actual, grader_cli, grader_timeout)
        for key in judge_specs:
            holds, note = grades.get(key, (None, "no verdict returned by grader"))
            if holds is None:
                ok = False
                notes.append(f"{key}: {note}")
            elif holds != judge_expected[key]:
                detail = f" ({note})" if note else ""
                notes.append(f"{key}: judge says property={holds}, expected {judge_expected[key]}{detail}")
                ok = False

    return ok, notes


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
    """Run ``cli`` with ``prompt`` on stdin. Return (stdout, stderr, rc).

    The command string is tokenised with ``shlex.split`` and executed with
    ``shell=False``. The operator supplies the command, so trust is not the
    issue — using an argv list rather than a shell string keeps prompt content
    (which can be attacker-controlled when an eval exercises an injection
    case) firmly on stdin and well away from any shell interpretation, and
    removes a class of accidental-metacharacter footgun in the operator's
    command. Operators who need shell features (pipes, redirections, env-var
    prefixes) should wrap their command in ``bash -c '<pipeline>'``.
    """
    proc = subprocess.run(
        shlex.split(cli),
        input=prompt,
        capture_output=True,
        text=True,
        shell=False,
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


def collect_tag_counts(cases: list[tuple[Path, Path]]) -> dict[str, int]:
    """Return how many discovered cases carry each tag."""
    counts: dict[str, int] = {}
    for case_dir, _fixtures_dir in cases:
        for tag in load_case_tags(case_dir):
            counts[tag] = counts.get(tag, 0) + 1
    return counts


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
        "--grader-cli",
        type=str,
        default=DEFAULT_GRADER_CLI,
        help=(
            "Shell command for a cheap judge model that grades free-text "
            "fields (rationale, reason, drop_reason, blockers, etc.). "
            "Prose fields are compared via a rubric prompt instead of "
            "exact equality; decision fields stay on exact compare. The set "
            "of prose fields is the runner's default plus any per-fixtures "
            "grading-schema.json overrides. Requires --cli. Default: "
            f"'{DEFAULT_GRADER_CLI}'. Pass --exact to disable grading."
        ),
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help=(
            "Disable the field-aware grader and require verbatim JSON "
            "equality on every field (the runner's pre-grader behaviour)."
        ),
    )
    parser.add_argument(
        "--grader-timeout",
        type=int,
        default=60,
        help="Timeout in seconds for each --grader-cli invocation (default: 60).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="In --cli mode, also print the prompts and the model's raw stdout per case.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help=("Stops on the first failure instead of running all cases. Only applies in --cli mode; "),
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
    parser.add_argument(
        "--list-tags",
        action="store_true",
        help=(
            "Print every distinct tag declared in case-meta.json under path, "
            "with the number of cases carrying each tag, and exit without "
            "running prompts."
        ),
    )
    args = parser.parse_args(argv)

    grader_explicit = args.grader_cli != DEFAULT_GRADER_CLI
    if args.cli is None and (grader_explicit or args.exact):
        parser.error("--grader-cli and --exact require --cli")

    cases = find_cases(args.path)
    if args.list_tags:
        tag_counts = collect_tag_counts(cases)
        if not tag_counts:
            print("no tags found")
            return 0
        for tag in sorted(tag_counts):
            print(f"{tag} {tag_counts[tag]}")
        return 0

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
    # Cache the prose-field schema per fixtures dir (config only, not grader results).
    _grading_schema_cache: dict[Path, set[str]] = {}
    # Cache the structural-assertion specs per fixtures dir.
    _assertions_cache: dict[Path, dict[str, dict]] = {}

    passed = failed = manual = errored = 0

    for case_dir, fixtures_dir in cases:
        if (args.cli is not None) and args.fail_fast and (failed or errored):
            print("Fail-fast enabled; stopping on first failure or error.")
            break
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
        structural = isinstance(expected, dict) and is_structural_expected(expected)
        assertions: dict[str, dict] = {}
        if structural:
            if fixtures_dir not in _assertions_cache:
                _assertions_cache[fixtures_dir] = load_assertions(fixtures_dir)
            assertions = _assertions_cache[fixtures_dir]
            if not assertions:
                # No assertions.json: preserve the manual-review fallback.
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
            if args.exact:
                print(f"ERROR   {case_label} (CLI exited {rc}; stderr: {stderr.strip()[:200]})")
                errored += 1
                if args.verbose:
                    print("--- STDOUT ---")
                    print(stdout)
                continue
            # Field-aware mode: a non-zero exit (often a refusal or a CLI
            # safety filter) is wrapped just like a no-JSON case. The
            # intersection-only comparator decides whether this case still
            # passes based on the keys expected.json declares. Wrap is a
            # silent implementation detail — the case still reports as
            # PASS or FAIL like any other.
            actual = {"raw_output": stdout, "stderr": stderr, "exit_code": rc}
        else:
            actual, parse_err = extract_json_from_output(stdout)
            if parse_err is not None:
                if args.exact:
                    # Exact mode requires literal JSON; non-JSON is an error.
                    print(f"ERROR   {case_label} ({parse_err})")
                    errored += 1
                    if args.verbose:
                        print("--- STDOUT ---")
                        print(stdout)
                    continue
                # Field-aware mode: wrap the prose as a synthetic object so
                # the intersection-only comparator can proceed. A model that
                # produced prose-only output will PASS unless expected.json
                # asserts on `raw_output`.
                actual = {"raw_output": stdout}

        if structural:
            if fixtures_dir not in _grading_schema_cache:
                _grading_schema_cache[fixtures_dir] = load_grading_schema(fixtures_dir)
            ok, notes = compare_structural(
                actual,
                expected,
                assertions,
                prose_fields=_grading_schema_cache[fixtures_dir],
                grader_cli=args.grader_cli,
                exact=args.exact,
                grader_timeout=args.grader_timeout,
            )
            if ok:
                print(f"PASS    {case_label}")
                passed += 1
            else:
                print(f"FAIL    {case_label}")
                for note in notes:
                    print(f"  {note}")
                failed += 1
        elif not args.exact:
            if fixtures_dir not in _grading_schema_cache:
                _grading_schema_cache[fixtures_dir] = load_grading_schema(fixtures_dir)
            prose_fields = _grading_schema_cache[fixtures_dir]
            ok, notes = compare_with_grader(
                actual,
                expected,
                prose_fields=prose_fields,
                grader_cli=args.grader_cli,
                timeout=args.grader_timeout,
            )
            if ok:
                print(f"PASS    {case_label}")
                passed += 1
            else:
                print(f"FAIL    {case_label}")
                for note in notes:
                    print(f"  {note}")
                failed += 1
        else:
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
