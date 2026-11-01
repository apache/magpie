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

"""Validate spec files in tools/spec-loop/specs/.

Checks every .md file that carries a YAML frontmatter block:

1. Required frontmatter keys — title, status, kind, mode, source, acceptance.
2. Valid ``status`` value — stable | experimental | proposed | off.
3. Valid ``kind`` value  — feature | fix | docs | chore.
4. Valid ``mode`` value  — Triage | Mentoring | Drafting | Pairing | infra.
5. Non-empty ``acceptance`` list — at least one ``- item`` entry.
6. Required body sections — What it does, Where it lives,
   Behaviour & contract, Out of scope, Acceptance criteria, Validation,
   Known gaps.
7. Validation section contains at least one fenced code block.
8. SPDX license header — every spec file must carry the Apache-2.0 SPDX
   identifier (``<!-- SPDX-License-Identifier: Apache-2.0``) before the
   opening ``---`` frontmatter delimiter.
9. Validation-path existence — every filesystem path referenced by a
   shell pattern (``--project``, ``--directory``, ``bash -n``,
   ``shellcheck``, ``test -f``) in a Validation code block must exist
   under the repository root. Catches stale paths after renames.
10. Spec-loop runner fixtures — when present, execute the deterministic
    Bash fixture suite for prompt assembly, harness argv construction, and
    ``.last-sync`` marker helpers.
11. Known-gap close conditions (``validate_gap_predicates``) — a Known-gap
    bullet may carry ``<!-- gap-closes-when: <predicate> -->``. HARD when
    the predicate already holds (the bullet describes shipped work) or is
    malformed or unresolvable; SOFT when a bullet carries none.
12. Cross-spec family counts (``validate_cross_spec_counts``) — a sentence
    naming a multi-word family (``repo-health``) next to a count of skills
    (``six-skill``, ``10 skills``) is a claim; HARD when two specs claim
    different counts for one family, or a claim differs from the number of
    ``SKILL.md`` files carrying that ``family:``.

SOFT advisories are printed but never fail the run (spec-gap-staleness.md).

Files without frontmatter (README.md, overview.md) are skipped silently.

Run from repo root::

    uv run --project tools/spec-validator --group dev pytest tools/spec-validator/tests/
    uv run --project tools/spec-validator spec-validate tools/spec-loop/specs/
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_FRONTMATTER_KEYS: frozenset[str] = frozenset(
    {"title", "status", "kind", "mode", "source", "acceptance"}
)
ALLOWED_STATUS: frozenset[str] = frozenset({"stable", "experimental", "proposed", "off"})
ALLOWED_KIND: frozenset[str] = frozenset({"feature", "fix", "docs", "chore"})
ALLOWED_MODE: frozenset[str] = frozenset({"Triage", "Mentoring", "Drafting", "Pairing", "infra"})

REQUIRED_SECTIONS: tuple[str, ...] = (
    "What it does",
    "Where it lives",
    "Behaviour & contract",
    "Out of scope",
    "Acceptance criteria",
    "Validation",
    "Known gaps",
)

# Every spec .md file must carry this SPDX identifier before the frontmatter.
SPDX_MARKER = "SPDX-License-Identifier: Apache-2.0"

DEFAULT_SPEC_DIR = Path("tools/spec-loop/specs")

_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_FENCED_CODE_RE = re.compile(r"^ {0,3}```[\s\S]*?^ {0,3}```", re.MULTILINE)
_YAML_BLOCK_SCALAR_HEADERS: frozenset[str] = frozenset({"|", ">", "|-", "|+", ">-", ">+"})

# ---------------------------------------------------------------------------
# Validation-path check constants (check #9)
# ---------------------------------------------------------------------------

# Patterns that extract filesystem paths from shell validation commands.
# Each tuple is (compiled regex with one capturing group, human-readable label).
_VALIDATION_PATH_EXTRACTORS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"--(?:project|directory)\s+(\S+)"), "uv --project/--directory"),
    (re.compile(r"\bbash\s+-n\s+(\S+)"), "bash -n"),
    (re.compile(r"\bshellcheck\s+(\S+)"), "shellcheck"),
    (re.compile(r"\btest\s+-f\s+(\S+)"), "test -f"),
]

# Characters that mark a captured path as a shell variable or placeholder token
# and should be silently skipped by the path-existence check.
_PATH_SKIP_CHARS: tuple[str, ...] = ("$", "<")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Violation:
    def __init__(self, path: Path, line: int | None, message: str, severity: str = "HARD") -> None:
        self.path = path
        self.line = line
        self.message = message
        self.severity = severity

    @property
    def hard(self) -> bool:
        return self.severity == "HARD"

    def __str__(self) -> str:
        prefix = "" if self.hard else f"{self.severity}: "
        if self.line is not None:
            return f"{prefix}{self.path}:{self.line}: {self.message}"
        return f"{prefix}{self.path}: {self.message}"


# ---------------------------------------------------------------------------
# Known-gap close conditions (spec-gap-staleness.md)
# ---------------------------------------------------------------------------

_GAP_PREDICATE_RE = re.compile(r"<!--\s*gap-closes-when:\s*(?P<pred>.*?)\s*-->", re.DOTALL)
_NARRATIVE = "none (narrative)"
_FAMILY_RE = re.compile(r"^family:[ \t]*(\S+)[ \t]*$", re.MULTILINE)


def known_gap_bullets(text: str) -> list[tuple[int, str]]:
    """Every top-level bullet of the ``## Known gaps`` section, with its line.

    A bullet runs from its ``- `` line to the next top-level bullet or the end
    of the section. Fenced code inside the section is skipped, so an example
    predicate quoted in a code block is never read as a real one.
    """
    lines = text.splitlines()
    in_section = False
    fence = False
    bullets: list[tuple[int, list[str]]] = []
    for number, line in enumerate(lines, start=1):
        if line.startswith("## "):
            if in_section:
                break
            in_section = line[3:].strip() == "Known gaps"
            continue
        if not in_section:
            continue
        if re.match(r"^ {0,3}(```|~~~)", line):
            fence = not fence
            continue
        if fence:
            continue
        if line.startswith("- "):
            bullets.append((number, [line]))
        elif bullets:
            # Indented continuation, a blank line, or a lazy continuation at
            # column 0 (a predicate comment written straight under the bullet).
            bullets[-1][1].append(line)
    return [(number, "\n".join(body).strip()) for number, body in bullets]


def skill_families(repo_root: Path) -> dict[str, list[str]]:
    """``family`` -> sorted skill names, from every ``skills/*/SKILL.md``."""
    families: dict[str, list[str]] = {}
    skills = repo_root / "skills"
    if not skills.is_dir():
        return families
    for skill_md in sorted(skills.glob("*/SKILL.md")):
        try:
            head = skill_md.read_text(encoding="utf-8")[:4000]
        except OSError:
            continue
        match = _FAMILY_RE.search(head)
        if match:
            families.setdefault(match.group(1), []).append(skill_md.parent.name)
    return families


def _is_test_file(file: Path) -> bool:
    return (
        "tests" in file.parts
        or file.name == "conftest.py"
        or file.name.startswith("test_")
        or file.name.endswith("_test.py")
    )


def _symbol_called(target: Path, name: str) -> tuple[bool, bool]:
    """``(defined, called)`` for ``name`` across the Python files under ``target``.

    A call only counts from production code: test files are skipped, and a
    call inside the definition of ``name`` itself (recursion) does not count,
    since either would mark a defined-but-unwired function as wired.
    """
    files = [target] if target.is_file() else sorted(target.rglob("*.py"))
    defined = called = False
    for file in files:
        if _is_test_file(file):
            continue
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        own = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name
        ]
        if own:
            defined = True
        own_ids = {id(sub) for node in own for sub in ast.walk(node)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and id(node) not in own_ids:
                func = node.func
                if (isinstance(func, ast.Name) and func.id == name) or (
                    isinstance(func, ast.Attribute) and func.attr == name
                ):
                    called = True
    return defined, called


def evaluate_gap_predicate(predicate: str, repo_root: Path) -> tuple[str, str]:
    """Return ``(state, detail)``: state is ``open``, ``closed`` or ``invalid``."""
    predicate = predicate.strip()
    if predicate == _NARRATIVE:
        return "open", "narrative"
    kind, sep, arg = predicate.partition(":")
    if not sep or not arg.strip():
        return "invalid", f"malformed predicate {predicate!r}"
    arg = arg.strip()
    if kind == "path-exists":
        if arg.startswith("/") or ".." in Path(arg).parts:
            return "invalid", f"path-exists needs a repository-relative path, got {arg!r}"
        if (repo_root / arg).exists():
            return "closed", f"{arg} exists"
        return "open", f"{arg} does not exist"
    if kind == "symbol-called":
        path, sep2, name = arg.partition("::")
        if not sep2 or not path or not name.isidentifier():
            return "invalid", f"symbol-called needs <path>::<name>, got {arg!r}"
        target = repo_root / path
        if not target.exists():
            return "invalid", f"symbol-called path {path} does not exist"
        if target.is_dir() and not any(target.rglob("*.py")):
            return "invalid", f"symbol-called path {path} has no Python files"
        defined, called = _symbol_called(target, name)
        if defined and called:
            return "closed", f"{name} is defined and called under {path}"
        return "open", f"{name} is {'defined but not called' if defined else 'not defined'} under {path}"
    if kind == "skill-count":
        family, sep2, count = arg.partition("=")
        family, count = family.strip(), count.strip()
        if not sep2 or not family or not count.isdigit():
            return "invalid", f"skill-count needs <family>=<n>, got {arg!r}"
        families = skill_families(repo_root)
        if family not in families:
            return "invalid", f"skill-count names family {family!r}, which no skill carries"
        live = len(families[family])
        if live == int(count):
            return "closed", f"{live} skills carry family:{family}"
        return "open", f"{live} skills carry family:{family}, not {count}"
    return (
        "invalid",
        f"unknown predicate kind {kind!r} (path-exists, symbol-called, skill-count, or {_NARRATIVE!r})",
    )


def validate_gap_predicates(path: Path, text: str, repo_root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for line, bullet in known_gap_bullets(text):
        found = _GAP_PREDICATE_RE.findall(bullet)
        title = _bullet_title(bullet)
        if not found:
            violations.append(
                Violation(
                    path,
                    line,
                    f"Known-gap bullet {title!r} has no close condition; add "
                    f"<!-- gap-closes-when: <predicate> --> or <!-- gap-closes-when: {_NARRATIVE} -->",
                    severity="SOFT",
                )
            )
            continue
        for predicate in found:
            state, detail = evaluate_gap_predicate(predicate, repo_root)
            if state == "closed":
                violations.append(
                    Violation(
                        path, line, f"Known-gap bullet {title!r} is closed ({detail}); remove or rewrite it"
                    )
                )
            elif state == "invalid":
                violations.append(Violation(path, line, f"Known-gap bullet {title!r}: {detail}"))
    return violations


def _bullet_title(bullet: str) -> str:
    first = bullet.splitlines()[0][2:].strip()
    bold = re.match(r"\*\*(.+?)\*\*", first)
    text = bold.group(1) if bold else first
    return text if len(text) <= 70 else text[:67] + "..."


# ---------------------------------------------------------------------------
# Cross-spec family counts (spec-gap-staleness.md)
# ---------------------------------------------------------------------------

_NUMBER_WORDS = {
    word: value
    for value, word in enumerate(
        [
            # "zero" and "one" are left out: "one skill per …" is not a
            # membership claim.
            "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
            "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
            "eighteen", "nineteen", "twenty",
        ],
        start=2,
    )
}  # fmt: skip
_COUNT_RE = re.compile(r"\b(?P<n>\d+|" + "|".join(_NUMBER_WORDS) + r")[- ]skills?\b", re.IGNORECASE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
# How many words may separate a family name from its count for the pair to be
# one claim ("Repo-health audits are now a six-skill family" is five apart).
# Farther apart, the count is about something else in the same sentence.
_CLAIM_WINDOW_WORDS = 6


def _prose(text: str) -> str:
    """Spec prose with code fences, HTML comments and inline code removed."""
    text = _FENCED_CODE_RE.sub("", _spec_body(text))
    text = _HTML_COMMENT_RE.sub("", text)
    text = _LINK_TARGET_RE.sub("]", text)
    return _INLINE_CODE_RE.sub("", text)


def family_count_claims(text: str, families: list[str]) -> list[tuple[str, int, str]]:
    """``(family, count, sentence)`` for every sentence that names a family and a count.

    Only multi-word families (``repo-health``, ``pr-management``) are matched:
    a one-word family name (``issue``, ``security``) is ordinary prose, and
    reading it as a family would be the prose inference the spec rules out.
    """
    # A file name (`contributor-growth.md`) or a plugin name (`magpie-pr-management`)
    # mentions the family's spec or package, not its membership.
    tokens = {
        family: re.compile(r"(?<![\w-])" + re.escape(family) + r"(?![\w-]|\.md\b)", re.IGNORECASE)
        for family in families
        if "-" in family
    }
    claims: list[tuple[str, int, str]] = []
    flat = re.sub(r"\s+", " ", _prose(text))
    for sentence in re.split(r"(?<=[.!?])\s+|\s+[\u2014\u2013]\s+|\|", flat):
        named = [(family, m) for family, token in tokens.items() for m in token.finditer(sentence)]
        if len({family for family, _m in named}) != 1:
            continue  # no family, or several: not an unambiguous claim
        family = named[0][0]
        # "<n> skills" / "<n>-skill", plus "<n> <family> skills".
        counts = list(_COUNT_RE.finditer(sentence)) + list(
            re.finditer(
                r"\b(?P<n>\d+|" + "|".join(_NUMBER_WORDS) + r")\s+" + re.escape(family) + r"\s+skills?\b",
                sentence,
                re.IGNORECASE,
            )
        )
        if not counts:
            continue
        for count in counts:
            near = any(
                len(sentence[min(m.end(), count.start()) : max(m.start(), count.end())].split())
                <= _CLAIM_WINDOW_WORDS
                for _family, m in named
            )
            if not near:
                continue
            raw = count.group("n")
            value = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw.lower()]
            claims.append((family, value, sentence.strip()))
    return claims


def validate_cross_spec_counts(spec_files: list[Path], repo_root: Path) -> list[Violation]:
    families = skill_families(repo_root)
    if not families:
        return []
    by_family: dict[str, list[tuple[Path, int, str]]] = {}
    texts: dict[Path, str] = {}
    for path in spec_files:
        try:
            texts[path] = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for family, count, sentence in family_count_claims(texts[path], sorted(families)):
            by_family.setdefault(family, []).append((path, count, sentence))
    violations: list[Violation] = []
    for family, claims in sorted(by_family.items()):
        live = families.get(family, [])
        claimed = sorted({count for _path, count, _s in claims})
        if claimed == [len(live)]:
            continue
        for path, count, sentence in claims:
            if count == len(live) and len(claimed) == 1:
                continue
            unnamed = [skill for skill in live if skill not in texts[path]]
            others = sorted({c for p, c, _s in claims if p != path and c != count})
            if count == len(live):
                # Right on its own, but another spec disagrees: at most one can be.
                parts = [f"claims {count} {family} skills, matching the {len(live)} SKILL.md files"]
            else:
                parts = [
                    f"claims {count} {family} skills, but {len(live)} SKILL.md files carry family:{family}"
                ]
            if others:
                parts.append(f"other specs claim {', '.join(map(str, others))}")
            if unnamed:
                parts.append(f"not named in this spec: {', '.join(unnamed)}")
            parts.append(f"claim: {sentence[:120]!r}")
            violations.append(Violation(path, None, "; ".join(parts)))
    return violations


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _frontmatter_bounds(text: str) -> tuple[int, int] | None:
    """Return (block_start, block_end) for the frontmatter content, or None.

    Handles files whose first non-whitespace content is an HTML comment
    (e.g. the SPDX license header) before the ``---`` delimiter.
    """
    idx = text.find("---\n")
    if idx == -1:
        return None
    # Verify only HTML comments / whitespace precede the opening ---
    prefix = text[:idx]
    clean = _HTML_COMMENT_RE.sub("", prefix).strip()
    if clean:
        return None
    try:
        end = text.index("\n---\n", idx + 4)
    except ValueError:
        return None
    return (idx + 4, end)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Return a dict of top-level frontmatter key→value, or None if absent."""
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return None
    block = text[bounds[0] : bounds[1]]

    result: dict[str, str] = {}
    current_key: str | None = None
    current_value_lines: list[str] = []

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if line == "":
            if current_key is not None:
                current_value_lines.append("")
            continue
        if not line.startswith((" ", "\t")) and ":" in line:
            if current_key is not None:
                result[current_key] = "\n".join(current_value_lines).strip()
            key, _, value = line.partition(":")
            current_key = key.strip()
            inline = value.strip()
            current_value_lines = [inline] if inline and inline not in _YAML_BLOCK_SCALAR_HEADERS else []
            continue
        if current_key is not None:
            stripped = line[2:] if line.startswith("  ") else line
            current_value_lines.append(stripped)

    if current_key is not None:
        result[current_key] = "\n".join(current_value_lines).strip()
    return result


def has_acceptance_items(text: str) -> bool:
    """Return True if the ``acceptance`` frontmatter key has at least one list item."""
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return False
    block = text[bounds[0] : bounds[1]]
    in_acceptance = False
    for line in block.splitlines():
        if not line.startswith((" ", "\t")) and ":" in line:
            in_acceptance = line.split(":", 1)[0].strip() == "acceptance"
            continue
        if in_acceptance and re.match(r"\s+-\s", line):
            return True
    return False


# ---------------------------------------------------------------------------
# Body section validation
# ---------------------------------------------------------------------------


def _spec_body(text: str) -> str:
    """Return the doc body — everything after the closing ``---`` frontmatter delimiter."""
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return text
    # body starts after "\n---\n"
    return text[bounds[1] + 5 :]


def extract_section_headings(text: str) -> set[str]:
    """Return the text of every ## heading in the spec body."""
    body = _spec_body(text)
    headings: set[str] = set()
    for line in body.splitlines():
        if line.startswith("## "):
            headings.add(line[3:].strip())
    return headings


def get_section_body(text: str, section: str) -> str | None:
    """Return the content of a named ## section, or None."""
    body = _spec_body(text)
    lines = body.splitlines()
    collecting = False
    collected: list[str] = []
    for line in lines:
        if line.startswith("## "):
            heading = line[3:].strip()
            if heading == section:
                collecting = True
                continue
            if collecting:
                break
        if collecting:
            collected.append(line)
    return "\n".join(collected) if collected else None


def validation_has_code_block(text: str) -> bool:
    """Return True if the Validation section contains at least one fenced code block."""
    section = get_section_body(text, "Validation")
    if not section:
        return False
    return bool(_FENCED_CODE_RE.search(section))


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_frontmatter(path: Path, text: str) -> list[Violation]:
    fm = parse_frontmatter(text)
    if fm is None:
        return []  # No frontmatter — not a spec file; skip silently

    violations: list[Violation] = []

    missing = REQUIRED_FRONTMATTER_KEYS - set(fm.keys())
    for key in sorted(missing):
        violations.append(Violation(path, 1, f"missing required frontmatter key: '{key}'"))

    if "status" in fm and fm["status"] not in ALLOWED_STATUS:
        violations.append(
            Violation(
                path,
                1,
                f"invalid status '{fm['status']}' — must be one of {sorted(ALLOWED_STATUS)}",
            )
        )

    if "kind" in fm and fm["kind"] not in ALLOWED_KIND:
        violations.append(
            Violation(
                path,
                1,
                f"invalid kind '{fm['kind']}' — must be one of {sorted(ALLOWED_KIND)}",
            )
        )

    if "mode" in fm and fm["mode"] not in ALLOWED_MODE:
        violations.append(
            Violation(
                path,
                1,
                f"invalid mode '{fm['mode']}' — must be one of {sorted(ALLOWED_MODE)}",
            )
        )

    if "acceptance" in fm and not has_acceptance_items(text):
        violations.append(
            Violation(path, 1, "acceptance key is present but has no list items (expected '  - ...')")
        )

    return violations


def validate_body(path: Path, text: str) -> list[Violation]:
    if parse_frontmatter(text) is None:
        return []  # Not a spec file

    violations: list[Violation] = []
    headings = extract_section_headings(text)

    for section in REQUIRED_SECTIONS:
        if section not in headings:
            violations.append(Violation(path, None, f"missing required section: '## {section}'"))

    if "Validation" in headings and not validation_has_code_block(text):
        violations.append(
            Violation(path, None, "Validation section has no fenced code block (expected ```...```)")
        )

    return violations


# ---------------------------------------------------------------------------
# SPDX header validation (check #8)
# ---------------------------------------------------------------------------


def validate_spdx_header(path: Path, text: str) -> list[Violation]:
    """Check that a spec file carries the Apache-2.0 SPDX license header.

    Every ``.md`` file that has a YAML frontmatter block (i.e. is a spec,
    not a README or overview) must contain ``SPDX-License-Identifier:
    Apache-2.0`` somewhere before the opening ``---`` delimiter.  Files
    without frontmatter are skipped silently — they are not spec files.
    """
    if parse_frontmatter(text) is None:
        return []  # Not a spec file; no SPDX required.

    if SPDX_MARKER not in text:
        return [
            Violation(
                path,
                1,
                f"missing SPDX license header — spec files must contain "
                f"'<!-- {SPDX_MARKER}' before the frontmatter delimiter; "
                f"see AGENTS.md § Commit and PR conventions",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Validation-path existence check (check #9)
# ---------------------------------------------------------------------------


def _join_line_continuations(text: str) -> str:
    r"""Join shell line-continuations (trailing ``\``) into single logical lines."""
    return re.sub(r"\\\n\s*", " ", text)


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from *start* (or CWD) to find the repository root.

    Uses the presence of a ``tools/`` directory as the canonical marker.
    Falls back to the starting path when no such ancestor is found.
    """
    cur = (start or Path.cwd()).resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / "tools").is_dir():
            return candidate
    return cur


def validate_validation_paths(path: Path, text: str, repo_root: Path | None = None) -> list[Violation]:
    """Check that filesystem paths in ## Validation code blocks exist on disk.

    Extracts path arguments from these shell patterns inside fenced code
    blocks of the ``## Validation`` section:

    - ``uv run --project <path>`` and ``uv run --directory <path>``
    - ``bash -n <file>``
    - ``shellcheck <file>``
    - ``test -f <file>``

    Paths containing ``$`` (shell variables) or ``<`` (placeholder tokens)
    are silently skipped. Bare tokens without a ``/`` are also skipped.
    Relative paths are resolved against the repository root.
    """
    if parse_frontmatter(text) is None:
        return []  # Not a spec file

    section_body = get_section_body(text, "Validation")
    if not section_body:
        return []

    root = repo_root or find_repo_root(path.parent)
    violations: list[Violation] = []

    for block_match in _FENCED_CODE_RE.finditer(section_body):
        block_text = _join_line_continuations(block_match.group())
        for pattern, label in _VALIDATION_PATH_EXTRACTORS:
            for m in pattern.finditer(block_text):
                raw = m.group(1).rstrip(";\\|&")
                if not raw:
                    continue
                # Skip shell variables and placeholder tokens
                if any(skip in raw for skip in _PATH_SKIP_CHARS):
                    continue
                # Skip bare command names without a path separator
                if "/" not in raw:
                    continue
                target = Path(raw) if Path(raw).is_absolute() else root / raw
                if not target.exists():
                    violations.append(
                        Violation(
                            path,
                            None,
                            f"validation command references missing path: {raw!r} "
                            f"(pattern: {label}; resolved to {target})",
                        )
                    )

    return violations


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def validate_file(path: Path, repo_root: Path | None = None) -> list[Violation]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [Violation(path, None, f"cannot read file: {exc}")]
    return (
        validate_spdx_header(path, text)
        + validate_frontmatter(path, text)
        + validate_body(path, text)
        + validate_validation_paths(path, text, repo_root=repo_root)
    )


def collect_spec_files(target: Path) -> list[Path]:
    """Return all .md files under *target* (or *target* itself if a file)."""
    if target.is_file():
        return [target]
    return sorted(target.rglob("*.md"))


def run_validation(target: Path, repo_root: Path | None = None) -> list[Violation]:
    root = repo_root or find_repo_root(target)
    violations: list[Violation] = []
    spec_files = collect_spec_files(target)
    for path in spec_files:
        violations.extend(validate_file(path, repo_root=root))
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if parse_frontmatter(text) is not None:
            violations.extend(validate_gap_predicates(path, text, root))
    violations.extend(validate_cross_spec_counts(spec_files, root))
    violations.extend(validate_spec_loop_runner_fixtures(root))
    return violations


def validate_spec_loop_runner_fixtures(repo_root: Path) -> list[Violation]:
    """Run deterministic fixture tests for the spec-loop runner when present."""
    fixture = repo_root / "tools" / "spec-loop" / "tests" / "test_runner_fixtures.sh"
    if not fixture.exists():
        return []

    result = subprocess.run(
        ["bash", str(fixture)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return []

    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    return [
        Violation(
            fixture.relative_to(repo_root),
            None,
            f"spec-loop runner fixture tests failed with exit code {result.returncode}: {output}",
        )
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate spec files.")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_SPEC_DIR),
        help="Spec file or directory to validate (default: tools/spec-loop/specs/)",
    )
    args = parser.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"spec-validator: path not found: {target}", file=sys.stderr)
        return 1

    violations = run_validation(target)
    hard = [v for v in violations if v.hard]
    soft = [v for v in violations if not v.hard]
    for v in soft:
        print(v)
    if soft:
        print(f"spec-validator: {len(soft)} SOFT advisory(ies) — informational, not blocking\n")
    if not hard:
        print("spec-validator: OK (no HARD violations)" if soft else "spec-validator: OK (no violations)")
        return 0

    print(f"spec-validator: {len(hard)} violation(s) found\n")
    for v in hard:
        print(v)
    return 1


if __name__ == "__main__":
    sys.exit(main())
