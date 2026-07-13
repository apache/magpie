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

"""Generate a compact routing inventory for the spec-loop.

The inventory is intentionally shallow: enough for an agent to choose the
next relevant files, not enough to replace direct verification. It is
stdlib-only so the loop can run it cheaply through ``uv``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SPECS_DIR = Path("tools/spec-loop/specs")
SKILLS_DIR = Path("skills")
TOOLS_DIR = Path("tools")

SKIP_SPEC_FILES = frozenset({"README.md", "overview.md"})
SKIP_TOOL_DIRS = frozenset({"spec-loop"})

_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_FENCED_CODE_RE = re.compile(r"^ {0,3}```(?:\w+)?\n([\s\S]*?)^ {0,3}```", re.MULTILINE)
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_SCRIPT_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*\"([^\"]+)\"", re.MULTILINE)
_SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
_YAML_BLOCK_SCALAR_HEADERS = frozenset({"|", ">", "|-", "|+", ">-", ">+"})

# Scope-map patterns — used by the spec-scope entry point.
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_SKILL_KEYWORD_RE = re.compile(r"\bSkill:\s*`([^`]+)`")


@dataclass
class SpecSummary:
    file: str
    title: str
    status: str
    mode: str
    kind: str
    where: list[str]
    validation: list[str]
    known_gaps: list[str]


@dataclass
class SkillSummary:
    file: str
    name: str
    mode: str
    capability: str
    organization: str
    description: str


@dataclass
class ToolSummary:
    path: str
    has_pyproject: bool
    has_tests: bool
    scripts: list[str]


@dataclass
class Inventory:
    specs: list[SpecSummary]
    skills: list[SkillSummary]
    tools: list[ToolSummary]


def find_repo_root(start: Path) -> Path:
    """Return the nearest parent containing .git."""
    path = start.resolve()
    while path != path.parent:
        if (path / ".git").exists():
            return path
        path = path.parent
    raise RuntimeError(f"Could not find repo root (.git) from {start}")


def _frontmatter_bounds(text: str) -> tuple[int, int] | None:
    idx = text.find("---\n")
    if idx == -1:
        return None
    if _HTML_COMMENT_RE.sub("", text[:idx]).strip():
        return None
    try:
        end = text.index("\n---\n", idx + 4)
    except ValueError:
        return None
    return (idx + 4, end)


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse top-level YAML-ish frontmatter without external dependencies."""
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return {}
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
            stripped = line[2:] if line.startswith("  ") else line.strip()
            current_value_lines.append(stripped)

    if current_key is not None:
        result[current_key] = "\n".join(current_value_lines).strip()
    return result


def _body_after_frontmatter(text: str) -> str:
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return text
    return text[bounds[1] + 5 :]


def get_section_body(text: str, section: str) -> str:
    """Return a ## section body, or an empty string."""
    body = _body_after_frontmatter(text)
    headings = list(_HEADING_RE.finditer(body))
    for index, match in enumerate(headings):
        if match.group(1).strip() != section:
            continue
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        return body[start:end].strip()
    return ""


def _compact_line(line: str) -> str:
    return " ".join(line.strip().split())


def _truncate(text: str, limit: int = 180) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def section_bullets(text: str, section: str, limit: int) -> list[str]:
    """Extract top-level bullets from a section."""
    body = get_section_body(text, section)
    bullets: list[str] = []
    current: list[str] = []

    def flush_current() -> None:
        if current and len(bullets) < limit:
            bullets.append(_truncate(_compact_line(" ".join(current))))
        current.clear()

    for line in body.splitlines():
        if len(bullets) >= limit:
            break
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            flush_current()
            current.append(stripped[2:])
            continue
        if current and stripped and not stripped.startswith(("```", "#")):
            current.append(stripped)
    flush_current()
    return bullets


def validation_commands(text: str, limit: int) -> list[str]:
    """Extract compact command lines from fenced blocks in Validation."""
    body = get_section_body(text, "Validation")
    commands: list[str] = []
    for block in _FENCED_CODE_RE.findall(body):
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            commands.append(_truncate(_compact_line(stripped), 220))
            if len(commands) >= limit:
                return commands
    return commands


def first_description_line(description: str) -> str:
    for line in description.splitlines():
        compact = _compact_line(line)
        if compact:
            return compact
    return ""


def compact_metadata_value(value: str) -> str:
    """Compact scalar or simple YAML-list frontmatter values for one-line output."""
    parts: list[str] = []
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        parts.append(stripped)
    return ", ".join(parts)


def load_specs(repo_root: Path, *, max_where: int, max_validation: int, max_gaps: int) -> list[SpecSummary]:
    specs_dir = repo_root / SPECS_DIR
    entries: list[SpecSummary] = []
    for path in sorted(specs_dir.glob("*.md")):
        if path.name in SKIP_SPEC_FILES:
            continue
        text = path.read_text()
        fm = parse_frontmatter(text)
        if not fm:
            continue
        entries.append(
            SpecSummary(
                file=str(path.relative_to(repo_root)),
                title=fm.get("title", path.stem),
                status=fm.get("status", ""),
                mode=fm.get("mode", ""),
                kind=fm.get("kind", ""),
                where=section_bullets(text, "Where it lives", max_where),
                validation=validation_commands(text, max_validation),
                known_gaps=section_bullets(text, "Known gaps", max_gaps),
            )
        )
    return entries


def load_skills(repo_root: Path) -> list[SkillSummary]:
    skills_dir = repo_root / SKILLS_DIR
    entries: list[SkillSummary] = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        text = path.read_text()
        fm = parse_frontmatter(text)
        if not fm.get("name"):
            continue
        entries.append(
            SkillSummary(
                file=str(path.relative_to(repo_root)),
                name=fm.get("name", path.parent.name),
                mode=compact_metadata_value(fm.get("mode", "")),
                capability=compact_metadata_value(fm.get("capability", "")),
                organization=compact_metadata_value(fm.get("organization", "")),
                description=first_description_line(fm.get("description", "")),
            )
        )
    return entries


def parse_project_scripts(pyproject_text: str) -> list[str]:
    """Return script names from the [project.scripts] table only."""
    scripts: list[str] = []
    in_scripts = False
    for line in pyproject_text.splitlines():
        section_match = _SECTION_RE.match(line.strip())
        if section_match:
            in_scripts = section_match.group(1) == "project.scripts"
            continue
        if not in_scripts:
            continue
        script_match = _SCRIPT_RE.match(line)
        if script_match:
            scripts.append(script_match.group(1))
    return scripts


def load_tools(repo_root: Path) -> list[ToolSummary]:
    tools_dir = repo_root / TOOLS_DIR
    entries: list[ToolSummary] = []
    for path in sorted(p for p in tools_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if path.name in SKIP_TOOL_DIRS:
            continue
        pyproject = path / "pyproject.toml"
        readme = path / "README.md"
        tests = path / "tests"
        if not pyproject.exists() and not readme.exists() and not tests.exists():
            continue
        scripts: list[str] = []
        if pyproject.exists():
            scripts = parse_project_scripts(pyproject.read_text())
        entries.append(
            ToolSummary(
                path=str(path.relative_to(repo_root)),
                has_pyproject=pyproject.exists(),
                has_tests=tests.is_dir(),
                scripts=scripts[:5],
            )
        )
    return entries


def build_inventory(repo_root: Path, *, max_where: int, max_validation: int, max_gaps: int) -> Inventory:
    return Inventory(
        specs=load_specs(repo_root, max_where=max_where, max_validation=max_validation, max_gaps=max_gaps),
        skills=load_skills(repo_root),
        tools=load_tools(repo_root),
    )


def _join(items: list[str]) -> str:
    return "; ".join(items) if items else "-"


def format_markdown(inventory: Inventory, *, brief: bool = False) -> str:
    lines = [
        "## Compact repository inventory",
        "",
        "Deterministic routing aid generated from local files. Use it to choose",
        "what to inspect next, but verify claims with direct file reads or code",
        "search before recording behaviour as present or absent.",
        "",
        "### Specs",
        "",
    ]
    for spec in inventory.specs:
        lines.append(f"- `{spec.file}` — {spec.title} [{spec.status}, {spec.mode}, {spec.kind}]")
        lines.append(f"  where: {_join(spec.where)}")
        lines.append(f"  validation: {_join(spec.validation)}")
        lines.append(f"  known gaps: {_join(spec.known_gaps)}")
    lines.extend(["", "### Skills", ""])
    for skill in inventory.skills:
        org = f", {skill.organization}" if skill.organization else ""
        summary = f"- `{skill.file}` — {skill.name} [{skill.mode}, {skill.capability}{org}]"
        if not brief and skill.description:
            summary += f": {skill.description}"
        lines.append(summary)
    lines.extend(["", "### Tools", ""])
    for tool in inventory.tools:
        markers = []
        if tool.has_pyproject:
            markers.append("pyproject")
        if tool.has_tests:
            markers.append("tests")
        script_suffix = f"; scripts: {', '.join(tool.scripts)}" if tool.scripts else ""
        lines.append(f"- `{tool.path}` — {', '.join(markers) if markers else 'metadata'}{script_suffix}")
    lines.append("")
    return "\n".join(lines)


def format_json(inventory: Inventory) -> str:
    return json.dumps(asdict(inventory), indent=2)


def extract_path_patterns(where_bullets: list[str]) -> frozenset[str]:
    """Extract normalised path prefixes from 'Where it lives' bullets.

    Returns a frozenset of path strings (no leading/trailing slashes) that
    can be used as prefix tests against changed-file paths.  Patterns come
    from two sources in each bullet:

    - Explicit skill names — ``Skill: `<name>``` bullets produce the pattern
      ``skills/<name>`` so that changes to ``skills/<name>/SKILL.md`` resolve
      to the right spec.
    - Backtick-quoted path tokens — any backtick-quoted token that contains
      a slash is treated as a path prefix directly.
    """
    patterns: set[str] = set()
    for bullet in where_bullets:
        for m in _SKILL_KEYWORD_RE.finditer(bullet):
            name = m.group(1).strip().rstrip("/")
            if "/" not in name:
                patterns.add(f"skills/{name}")
        for m in _BACKTICK_RE.finditer(bullet):
            token = m.group(1).strip().rstrip("/")
            if "/" in token:
                patterns.add(token.strip("/"))
    return frozenset(patterns)


def _changed_path_candidates(changed: str) -> list[str]:
    """Expand a changed path into one or more patterns to test against spec patterns.

    For ``.claude/skills/magpie-<name>`` symlink entries the runner records,
    also synthesise a ``skills/<name>`` alias so that skill-name patterns
    extracted from 'Skill: `<name>`' bullets resolve correctly.
    """
    normalised = changed.lstrip("/")
    candidates = [normalised]
    parts = normalised.split("/")
    if len(parts) >= 3 and parts[0] == ".claude" and parts[1] == "skills" and parts[2].startswith("magpie-"):
        skill_name = parts[2][len("magpie-") :]
        candidates.append("/".join(["skills", skill_name, *parts[3:]]))
    return candidates


def scope_map(changed_paths: list[str], repo_root: Path) -> list[str]:
    """Return spec file paths likely relevant to the given changed file paths.

    For each spec, path patterns are extracted from its 'Where it lives'
    bullets.  A spec is included if any of its patterns is a prefix of any
    candidate path derived from the changed list.  The result is sorted and
    deduplicated.

    Intended use: the spec-loop update beat pipes the output of
    ``git diff --name-only`` through ``spec-scope`` to focus the agent on
    the specs most likely to need re-inspection, rather than asking the
    agent to do that mapping from scratch.
    """
    specs = load_specs(repo_root, max_where=50, max_validation=0, max_gaps=0)
    spec_patterns: list[tuple[str, frozenset[str]]] = [
        (spec.file, extract_path_patterns(spec.where)) for spec in specs
    ]
    relevant: set[str] = set()
    for changed in changed_paths:
        for candidate in _changed_path_candidates(changed):
            for spec_file, patterns in spec_patterns:
                if spec_file in relevant:
                    continue
                for pattern in patterns:
                    if candidate == pattern or candidate.startswith(pattern + "/"):
                        relevant.add(spec_file)
                        break
    return sorted(relevant)


def scope_main(argv: list[str] | None = None) -> None:
    """CLI entry point: map changed paths to relevant spec files.

    Reads file paths from positional arguments or stdin (one per line) and
    writes the relevant spec file paths to stdout, one per line.  Empty
    input produces no output.  Exit code is always 0 so a pipeline that
    finds no matches does not fail a shell script.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Map changed file paths to likely relevant spec files for the "
            "spec-loop update beat.  Reads paths from positional arguments "
            "or stdin (one per line) and writes matching spec file paths to "
            "stdout."
        )
    )
    parser.add_argument("paths", nargs="*", help="Changed file paths.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: nearest .git parent).",
    )
    args = parser.parse_args(argv)

    if args.paths:
        changed = [p for p in args.paths if p]
    else:
        changed = [line.rstrip("\n") for line in sys.stdin if line.strip()]

    if not changed:
        return

    try:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    for spec in scope_map(changed, repo_root):
        print(spec)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate compact routing inventory for spec-loop prompts.")
    parser.add_argument(
        "--repo-root", type=Path, default=None, help="Repository root (default: nearest .git parent)."
    )
    parser.add_argument("--json", dest="as_json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument("--brief", action="store_true", help="Omit skill descriptions from Markdown output.")
    parser.add_argument("--max-where", type=int, default=3, help="Max Where-it-lives bullets per spec.")
    parser.add_argument("--max-validation", type=int, default=3, help="Max validation commands per spec.")
    parser.add_argument("--max-gaps", type=int, default=2, help="Max known-gap bullets per spec.")
    args = parser.parse_args()

    try:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    inventory = build_inventory(
        repo_root,
        max_where=args.max_where,
        max_validation=args.max_validation,
        max_gaps=args.max_gaps,
    )
    if args.as_json:
        print(format_json(inventory))
    else:
        print(format_markdown(inventory, brief=args.brief), end="")
