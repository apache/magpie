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

"""Deterministic structural diff between two skill trees.

Parses two ``SKILL.md`` files (and their sibling ``.md`` support files) into
normalised representations and emits a structured JSON diff.  The output
grounds the ``skill-reconciler`` skill's ALLOWED / DRIFT / SAFETY-BASELINE
classification in a deterministic object rather than raw prose.

Usage::

    uv run --project tools/skill-reconciler-diff \\
        skill-reconciler-diff skills/skill-a/SKILL.md skills/skill-b/SKILL.md

    # Or pass parent directories — the tool resolves SKILL.md inside:
    uv run --project tools/skill-reconciler-diff \\
        skill-reconciler-diff skills/skill-a skills/skill-b

Output: JSON on stdout.  Exit 0 on success; non-zero on parse errors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# YAML frontmatter parsing (stdlib-only, no PyYAML dependency)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract key: value pairs from a leading YAML frontmatter block.

    Supports only the simple ``key: value`` form (no nested objects, no
    multi-line values) because SKILL.md frontmatter follows that convention.
    Returns an empty dict when no frontmatter is found.
    """
    m = _FM_RE.match(text)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


# ---------------------------------------------------------------------------
# Fenced-code-block masking
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def _fenced_spans(text: str) -> list[tuple[int, int]]:
    """Return char-offset spans covered by fenced code blocks (``` or ~~~).

    A ``# heading`` or ``# Step N`` line inside a fenced code block is sample
    content, not a real heading — masking these keeps the structural diff from
    picking up phantom headings/steps in the code-block-heavy SKILL.md files.
    """
    spans: list[tuple[int, int]] = []
    fence: str | None = None  # opening run, e.g. "````"; a closer needs the same char and at least its length
    start = 0
    pos = 0
    for line in text.splitlines(keepends=True):
        m = _FENCE_RE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
                start = pos
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
            spans.append((start, pos + len(line)))
            fence = None
        pos += len(line)
    if fence is not None:  # unterminated fence runs to end of text
        spans.append((start, pos))
    return spans


def _in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    """True when char offset *pos* falls inside any of *spans*."""
    return any(s <= pos < e for s, e in spans)


# ---------------------------------------------------------------------------
# Section heading extraction
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$", re.MULTILINE)


def _parse_headings(text: str) -> list[tuple[int, str]]:
    """Return ordered list of (level, title) heading tuples from *text*.

    Headings inside fenced code blocks are ignored (see ``_fenced_spans``).
    """
    spans = _fenced_spans(text)
    return [
        (len(m.group(1)), m.group(2).strip())
        for m in _HEADING_RE.finditer(text)
        if not _in_spans(m.start(), spans)
    ]


# ---------------------------------------------------------------------------
# Step inventory extraction
# ---------------------------------------------------------------------------

# Start of any ATX heading (bare ``#`` included), for where a step section ends.
_SECTION_START_RE = re.compile(r"^(#{1,6})(?:[ \t]|$)", re.MULTILINE)

_STEP_HEADING_RE = re.compile(r"^#{1,3}\s+Step\s+(\S+)[^\n]*$", re.MULTILINE | re.IGNORECASE)


def _parse_steps(text: str) -> dict[str, str]:
    """Extract ``## Step N`` sections as {step_label: body_text}.

    A step body runs to the next heading of the same or a higher level.
    Step headings inside fenced code blocks are ignored; bodies are still
    sliced from the original text, so a step body keeps any code it contains.
    """
    spans = _fenced_spans(text)
    steps: dict[str, str] = {}
    matches = [m for m in _STEP_HEADING_RE.finditer(text) if not _in_spans(m.start(), spans)]
    headings = [m for m in _SECTION_START_RE.finditer(text) if not _in_spans(m.start(), spans)]
    for i, m in enumerate(matches):
        label = m.group(1).rstrip("—: ")
        start = m.end()
        level = len(m.group(0)) - len(m.group(0).lstrip("#"))
        end = next(
            (h.start() for h in headings if h.start() > m.start() and len(h.group(1)) <= level), len(text)
        )
        if i + 1 < len(matches):
            end = min(end, matches[i + 1].start())
        steps[label] = text[start:end].strip()
    return steps


# ---------------------------------------------------------------------------
# Placeholder inventory
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"<([a-z][a-z0-9-]*)>")


def _parse_placeholders(text: str) -> set[str]:
    """Return the set of ``<placeholder>`` tokens found in *text*."""
    return set(_PLACEHOLDER_RE.findall(text))


# ---------------------------------------------------------------------------
# Safety-baseline clause detection
# ---------------------------------------------------------------------------

# Clause 1 — untrusted content is never instructions (injection guard).
# Look for wording that establishes the "external content is data, not a directive" rule.
_CLAUSE1_RE = re.compile(
    r"(?:external content|untrusted content|external.{0,30}data.{0,30}never|"
    r"never.{0,40}instruction|injection.{0,30}attempt|prompt.injection|"
    r"treat.{0,40}as.{0,20}data|not.{0,30}an.{0,20}instruction)",
    re.IGNORECASE,
)

# Clause 2 — collaborator / identity-resolution caveats.
_CLAUSE2_RE = re.compile(
    r"(?:collaborator.{0,80}(?:instruct|direct|gate|only)|"
    r"(?:only|must).{0,60}collaborator|"
    r"non-collaborator|collaborator-trust|"
    r"tracker.{0,40}collaborator)",
    re.IGNORECASE,
)

# Clause 3 — confidentiality posture is not weakened.
_CLAUSE3_RE = re.compile(
    r"(?:never.{0,50}public.{0,50}surface|"
    r"confidential|embargoed|private.{0,40}(?:mail|list|content)|"
    r"not.{0,30}(?:reproduce|quote|appear).{0,40}public|"
    r"public surface)",
    re.IGNORECASE,
)


@dataclass
class SafetyBaseline:
    """Presence of each safety-baseline clause in a skill body."""

    clause_1_injection_guard: bool = False
    clause_2_collaborator_trust: bool = False
    clause_3_confidentiality_posture: bool = False


def _parse_safety_baseline(text: str) -> SafetyBaseline:
    """Detect which safety-baseline clauses are present in *text*."""
    body = text
    # Strip frontmatter so we only scan the skill body.
    body = _FM_RE.sub("", body, count=1)
    return SafetyBaseline(
        clause_1_injection_guard=bool(_CLAUSE1_RE.search(body)),
        clause_2_collaborator_trust=bool(_CLAUSE2_RE.search(body)),
        clause_3_confidentiality_posture=bool(_CLAUSE3_RE.search(body)),
    )


# ---------------------------------------------------------------------------
# Support-file collection
# ---------------------------------------------------------------------------


def _collect_support_files(skill_path: Path) -> list[str]:
    """Return sorted list of ``.md`` file names sibling to *skill_path*."""
    parent = skill_path.parent
    return sorted(p.name for p in parent.glob("*.md") if p.name != skill_path.name)


# ---------------------------------------------------------------------------
# Parsed skill representation
# ---------------------------------------------------------------------------


@dataclass
class ParsedSkill:
    path: str
    frontmatter: dict[str, str]
    section_headings: list[tuple[int, str]]
    step_inventory: dict[str, str]
    placeholder_inventory: list[str]
    support_files: list[str]
    safety_baseline: SafetyBaseline


def _resolve_skill_path(raw: str) -> Path:
    """Resolve *raw* to a readable SKILL.md path.

    Accepts either a direct path to ``SKILL.md`` or a directory that
    contains one.  Raises ``FileNotFoundError`` when neither resolves.
    """
    p = Path(raw)
    if p.is_dir():
        candidate = p / "SKILL.md"
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"No SKILL.md found in directory: {p}")
    if p.is_file():
        return p
    raise FileNotFoundError(f"Path does not exist: {p}")


def parse_skill(raw_path: str) -> ParsedSkill:
    """Parse a skill tree rooted at *raw_path* into a ``ParsedSkill``."""
    skill_path = _resolve_skill_path(raw_path)
    text = skill_path.read_text(encoding="utf-8")
    placeholders = _parse_placeholders(text)
    return ParsedSkill(
        path=str(skill_path),
        frontmatter=_parse_frontmatter(text),
        section_headings=_parse_headings(text),
        step_inventory=_parse_steps(text),
        placeholder_inventory=sorted(placeholders),
        support_files=_collect_support_files(skill_path),
        safety_baseline=_parse_safety_baseline(text),
    )


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------


@dataclass
class FrontmatterDiff:
    """Differences in YAML frontmatter between two skills."""

    only_in_a: dict[str, str] = field(default_factory=dict)
    only_in_b: dict[str, str] = field(default_factory=dict)
    changed: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def has_diff(self) -> bool:
        return bool(self.only_in_a or self.only_in_b or self.changed)


@dataclass
class SectionHeadingsDiff:
    """Differences in section-heading inventory and order."""

    only_in_a: list[str] = field(default_factory=list)
    only_in_b: list[str] = field(default_factory=list)
    order_changed: bool = False

    @property
    def has_diff(self) -> bool:
        return bool(self.only_in_a or self.only_in_b or self.order_changed)


@dataclass
class StepDiff:
    """Differences in the step inventory."""

    only_in_a: list[str] = field(default_factory=list)
    only_in_b: list[str] = field(default_factory=list)
    body_changed: list[str] = field(default_factory=list)

    @property
    def has_diff(self) -> bool:
        return bool(self.only_in_a or self.only_in_b or self.body_changed)


@dataclass
class PlaceholderDiff:
    """Differences in placeholder token inventory."""

    only_in_a: list[str] = field(default_factory=list)
    only_in_b: list[str] = field(default_factory=list)

    @property
    def has_diff(self) -> bool:
        return bool(self.only_in_a or self.only_in_b)


@dataclass
class SupportFilesDiff:
    """Differences in sibling support-file inventory."""

    only_in_a: list[str] = field(default_factory=list)
    only_in_b: list[str] = field(default_factory=list)

    @property
    def has_diff(self) -> bool:
        return bool(self.only_in_a or self.only_in_b)


@dataclass
class ClauseDiff:
    """Per-clause safety-baseline presence comparison."""

    a_present: bool
    b_present: bool

    @property
    def diverges(self) -> bool:
        return self.a_present != self.b_present


@dataclass
class SafetyBaselineDiff:
    """Safety-baseline clause presence diff between two skills."""

    clause_1_injection_guard: ClauseDiff = field(default_factory=lambda: ClauseDiff(False, False))
    clause_2_collaborator_trust: ClauseDiff = field(default_factory=lambda: ClauseDiff(False, False))
    clause_3_confidentiality_posture: ClauseDiff = field(default_factory=lambda: ClauseDiff(False, False))

    @property
    def has_divergence(self) -> bool:
        return (
            self.clause_1_injection_guard.diverges
            or self.clause_2_collaborator_trust.diverges
            or self.clause_3_confidentiality_posture.diverges
        )


@dataclass
class StructuralDiff:
    """Complete structural diff between two parsed skills."""

    skill_a_path: str
    skill_b_path: str
    identical: bool
    frontmatter_diff: FrontmatterDiff
    section_headings_diff: SectionHeadingsDiff
    step_diff: StepDiff
    placeholder_diff: PlaceholderDiff
    support_files_diff: SupportFilesDiff
    safety_baseline_diff: SafetyBaselineDiff


def _diff_frontmatter(a: dict[str, str], b: dict[str, str]) -> FrontmatterDiff:
    keys_a, keys_b = set(a), set(b)
    # Sort every set-derived sequence so the output is byte-for-byte
    # deterministic regardless of PYTHONHASHSEED (str set-iteration order is
    # seed-dependent). Every other diff dimension already sorts its output.
    diff = FrontmatterDiff(
        only_in_a={k: a[k] for k in sorted(keys_a - keys_b)},
        only_in_b={k: b[k] for k in sorted(keys_b - keys_a)},
    )
    for k in sorted(keys_a & keys_b):
        if a[k] != b[k]:
            diff.changed[k] = {"a": a[k], "b": b[k]}
    return diff


def _diff_section_headings(a: list[tuple[int, str]], b: list[tuple[int, str]]) -> SectionHeadingsDiff:
    titles_a = [t for _, t in a]
    titles_b = [t for _, t in b]
    set_a, set_b = set(titles_a), set(titles_b)
    common = set_a & set_b
    order_changed = [t for t in titles_a if t in common] != [t for t in titles_b if t in common]
    return SectionHeadingsDiff(
        only_in_a=sorted(set_a - set_b),
        only_in_b=sorted(set_b - set_a),
        order_changed=order_changed,
    )


def _diff_steps(a: dict[str, str], b: dict[str, str]) -> StepDiff:
    keys_a, keys_b = set(a), set(b)
    body_changed = [k for k in keys_a & keys_b if a[k] != b[k]]
    return StepDiff(
        only_in_a=sorted(keys_a - keys_b),
        only_in_b=sorted(keys_b - keys_a),
        body_changed=sorted(body_changed),
    )


def _diff_safety_baseline(a: SafetyBaseline, b: SafetyBaseline) -> SafetyBaselineDiff:
    return SafetyBaselineDiff(
        clause_1_injection_guard=ClauseDiff(a.clause_1_injection_guard, b.clause_1_injection_guard),
        clause_2_collaborator_trust=ClauseDiff(a.clause_2_collaborator_trust, b.clause_2_collaborator_trust),
        clause_3_confidentiality_posture=ClauseDiff(
            a.clause_3_confidentiality_posture, b.clause_3_confidentiality_posture
        ),
    )


def diff_skills(a: ParsedSkill, b: ParsedSkill) -> StructuralDiff:
    """Compute the structural diff between two parsed skills."""
    fm_diff = _diff_frontmatter(a.frontmatter, b.frontmatter)
    hdg_diff = _diff_section_headings(a.section_headings, b.section_headings)
    step_diff = _diff_steps(a.step_inventory, b.step_inventory)
    ph_diff = PlaceholderDiff(
        only_in_a=sorted(set(a.placeholder_inventory) - set(b.placeholder_inventory)),
        only_in_b=sorted(set(b.placeholder_inventory) - set(a.placeholder_inventory)),
    )
    sf_diff = SupportFilesDiff(
        only_in_a=sorted(set(a.support_files) - set(b.support_files)),
        only_in_b=sorted(set(b.support_files) - set(a.support_files)),
    )
    sb_diff = _diff_safety_baseline(a.safety_baseline, b.safety_baseline)

    identical = not any(
        [
            fm_diff.has_diff,
            hdg_diff.has_diff,
            step_diff.has_diff,
            ph_diff.has_diff,
            sf_diff.has_diff,
            sb_diff.has_divergence,
        ]
    )
    return StructuralDiff(
        skill_a_path=a.path,
        skill_b_path=b.path,
        identical=identical,
        frontmatter_diff=fm_diff,
        section_headings_diff=hdg_diff,
        step_diff=step_diff,
        placeholder_diff=ph_diff,
        support_files_diff=sf_diff,
        safety_baseline_diff=sb_diff,
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _coerce_tuples(obj: Any) -> Any:
    """Convert tuples to lists so JSON serialisation is stable."""
    if isinstance(obj, dict):
        return {k: _coerce_tuples(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_coerce_tuples(item) for item in obj]
    return obj


def render_json(diff: StructuralDiff) -> str:
    """Return pretty-printed JSON representation of *diff*."""
    return json.dumps(_coerce_tuples(asdict(diff)), indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``skill-reconciler-diff`` CLI."""
    parser = argparse.ArgumentParser(
        prog="skill-reconciler-diff",
        description=(
            "Parse two skill trees and emit a structural JSON diff for use by the skill-reconciler skill."
        ),
    )
    parser.add_argument(
        "skill_a",
        metavar="SKILL_A",
        help="Path to the first SKILL.md or its parent directory.",
    )
    parser.add_argument(
        "skill_b",
        metavar="SKILL_B",
        help="Path to the second SKILL.md or its parent directory.",
    )
    args = parser.parse_args(argv)

    try:
        a = parse_skill(args.skill_a)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        b = parse_skill(args.skill_b)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(render_json(diff_skills(a, b)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
