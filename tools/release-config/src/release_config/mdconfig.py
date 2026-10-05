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
"""Locate and parse the adopter's release-management markdown config.

The config files are prose documents with `| key | value |` tables, a few
free-form sections (`release-build.md § Digest set`, `§ Expected artefact
list`, `§ Build invocation`), one fenced YAML list
(`§ Convenience artefacts`) and a roster table (`pmc-roster.md`). Example
content is always blockquoted (`> …`) or follows a `Template guidance` /
`Example shape:` lead-in in the templates, so it is skipped.

`<project-config>` resolves **per file, personal first**: each layer of
`layers.config_layers` in turn — the personal layer (`.apache-magpie-local/`
in an adopted repository, `<git-common-dir>/apache-magpie/` otherwise, then
a legacy in-tree `.apache-magpie-local/`), then `.apache-magpie-overrides/`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from release_config.layers import config_layers

PROJECT_CONFIG_PREFIX = "<project-config>/"

_KEY_CELL = re.compile(r"^`([a-z_][a-z0-9_.]*)`$")
_BACKTICK = re.compile(r"`([^`]+)`")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE = re.compile(r"^\s*(?:>\s*)?(```|~~~)")
_SKIP_LEADS = ("template guidance", "example shape")

# Keys whose value is a list even when it holds a single item.
LIST_KEYS = frozenset(
    {
        "version_manifest_files",
        "announce_cc_lists",
        "site_pr_files",
        "expected_artefacts",
        "digest_set",
        "category_x_dependencies",
    }
)


# --------------------------------------------------------------------------- files


@dataclass
class Resolver:
    """Find `<project-config>` files and paths the config names."""

    project_root: Path
    config_dir: Path | None = None

    def find(self, name: str) -> Path | None:
        if self.config_dir is not None:
            path = self.config_dir / name
            return path if path.is_file() else None
        for layer in config_layers(self.project_root):
            path = layer / name
            if path.is_file():
                return path
        return None

    def resolve_ref(self, value: str) -> Path | None:
        """A path written in the config: `<project-config>/x.md` or repo-relative."""
        if value.startswith(PROJECT_CONFIG_PREFIX):
            return self.find(value[len(PROJECT_CONFIG_PREFIX) :])
        path = Path(value)
        if not path.is_absolute():
            path = self.project_root / path
        return path if path.is_file() else None

    def display(self, path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            return str(path.relative_to(self.project_root))
        except ValueError:
            return str(path)


def read_text(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


# --------------------------------------------------------------------------- markdown


def _strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _live_lines(text: str) -> list[tuple[str, bool]]:
    """(line, inside_fence) for every line, HTML comments removed."""
    out: list[tuple[str, bool]] = []
    inside = False
    for line in _strip_comments(text).splitlines():
        if _FENCE.match(line):
            out.append((line, True))
            inside = not inside
            continue
        out.append((line, inside))
    return out


def parse_value(raw: str, key: str = "") -> Any:
    """Normalise one table value cell.

    `*(…)*` notes mean unset; backticked tokens before the first note are the
    value (two or more make a list); anything else is plain text.
    """
    cell = raw.strip()
    if not cell or cell.startswith("*(") or cell.startswith("_(") or cell in {"—", "-"}:
        return [] if key in LIST_KEYS else None
    head = re.split(r"\s\*\(|\s—\s|\s--\s", cell, maxsplit=1)[0]
    tokens = _BACKTICK.findall(head)
    if tokens:
        if len(tokens) > 1 or key in LIST_KEYS:
            return [t.strip() for t in tokens]
        return tokens[0].strip()
    text = head.strip()
    if key in LIST_KEYS:
        return [part.strip() for part in text.split(",") if part.strip()]
    return text


def table_values(text: str | None) -> dict[str, Any]:
    """Every `| \\`key\\` | value |` row outside code fences and blockquotes; first row wins."""
    values: dict[str, Any] = {}
    if not text:
        return values
    for line, inside in _live_lines(text):
        if inside or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        match = _KEY_CELL.match(cells[0])
        if not match or match.group(1) in values:
            continue
        values[match.group(1)] = parse_value(cells[1], match.group(1))
    return values


def section_lines(text: str | None, title: str) -> list[str] | None:
    """Lines under the first heading whose text contains `title` (case-insensitive)."""
    if not text:
        return None
    lines = _strip_comments(text).splitlines()
    start = level = None
    inside = False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            inside = not inside
            continue
        if inside:
            continue
        match = _HEADING.match(line)
        if not match:
            continue
        depth = len(match.group(1))
        if start is None:
            if title.lower() in match.group(2).lower():
                start, level = index + 1, depth
        elif level is not None and depth <= level:
            return lines[start:index]
    return None if start is None else lines[start:]


def _blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Split section lines into ('fence'|'quote'|'table'|'text', lines) blocks."""
    blocks: list[tuple[str, list[str]]] = []
    current: list[str] = []
    kind = ""
    inside = False

    def flush() -> None:
        nonlocal current, kind
        if current:
            blocks.append((kind, current))
        current, kind = [], ""

    for line in lines:
        stripped = line.strip()
        if inside:
            current.append(line)
            if _FENCE.match(line):
                inside = False
                flush()
            continue
        if _FENCE.match(line):
            flush()
            kind = "quote" if stripped.startswith(">") else "fence"
            current = [line]
            inside = True
            continue
        if not stripped:
            flush()
            continue
        line_kind = "quote" if stripped.startswith(">") else "table" if stripped.startswith("|") else "text"
        if current and line_kind != kind:
            flush()
        kind = line_kind
        current.append(line)
    flush()
    return blocks


def first_text_block(lines: list[str] | None) -> str | None:
    """The section's own value: its first prose / bullet block.

    `None` when the section is missing, empty, or still the template's
    `TODO:` placeholder. Blockquoted examples, fences and tables are skipped,
    as are `Template guidance` / `Example shape` lead-ins.
    """
    if lines is None:
        return None
    for kind, block in _blocks(lines):
        if kind != "text":
            continue
        joined = " ".join(part.strip() for part in block)
        lowered = joined.lower()
        if lowered.startswith("todo"):
            return None
        if lowered.startswith(_SKIP_LEADS):
            return None
        return joined
    return None


def first_fence(lines: list[str] | None, language: str | None = None) -> str | None:
    """Content of the first non-blockquoted fenced block (optionally of a language)."""
    if lines is None:
        return None
    for kind, block in _blocks(lines):
        if kind != "fence":
            continue
        opener = block[0].strip().lstrip("`~").strip().lower()
        if language is not None and opener != language:
            continue
        body = block[1:-1] if len(block) > 1 and _FENCE.match(block[-1]) else block[1:]
        return "\n".join(body).strip("\n")
    return None


def backtick_tokens(text: str | None) -> list[str]:
    return [t.strip() for t in _BACKTICK.findall(text or "")]


def is_placeholder(value: Any) -> bool:
    """A template value nobody filled in: `<dev-list>`, `TODO…`."""
    if isinstance(value, list):
        return bool(value) and all(is_placeholder(v) for v in value)
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return bool(re.fullmatch(r"<[^<>]+>", stripped)) or "TODO" in stripped


# --------------------------------------------------------------------------- yaml-ish


def _scalar(raw: str) -> Any:
    value = raw.strip()
    if value in {"", "~", "null", "Null", "NULL"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value == "[]":
        return []
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _drop_comment(raw: str) -> str:
    quote = ""
    for index, char in enumerate(raw):
        if char in "\"'" and not quote:
            quote = char
        elif char == quote:
            quote = ""
        elif char == "#" and not quote and (index == 0 or raw[index - 1].isspace()):
            return raw[:index].rstrip()
    return raw.rstrip()


def parse_yaml_list(text: str, key: str) -> list[dict[str, Any]] | None:
    """Parse `key:` followed by a list of flat mappings (block scalars and nested lists allowed).

    Enough YAML for `convenience_artefacts`; returns `None` when `key` is absent.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = _drop_comment(line)
        if re.fullmatch(rf"{re.escape(key)}:\s*(\[\])?", stripped.strip()):
            if stripped.strip().endswith("[]"):
                return []
            return _parse_entries(lines[index + 1 :])
    return None


def _parse_entries(lines: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    index = 0
    while index < len(lines):
        raw = lines[index]
        if not raw.strip() or raw.strip().startswith("#"):
            index += 1
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent == 0:
            break
        body = raw.strip()
        if body.startswith("- ") and (current is None or indent <= current.get("__indent__", indent)):
            current = {"__indent__": indent}
            entries.append(current)
            body = body[2:]
            indent += 2
        if current is None:
            index += 1
            continue
        match = re.match(r"([A-Za-z_][\w-]*):(.*)$", body)
        if not match:
            index += 1
            continue
        name, rest = match.group(1), _drop_comment(match.group(2)).strip()
        index += 1
        if rest in {"|", "|-", ">", ">-"}:
            block: list[str] = []
            while index < len(lines) and (not lines[index].strip() or len(lines[index]) - len(lines[index].lstrip()) > indent):
                block.append(lines[index])
                index += 1
            width = min((len(b) - len(b.lstrip()) for b in block if b.strip()), default=0)
            joined = "\n".join(b[width:] for b in block).strip("\n")
            current[name] = joined if rest.startswith("|") else " ".join(joined.split())
            continue
        if rest == "":
            items: list[Any] = []
            while index < len(lines):
                nxt = lines[index]
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt.strip().startswith("- ") and nxt_indent > indent:
                    items.append(_scalar(_drop_comment(nxt.strip()[2:])))
                    index += 1
                    continue
                break
            current[name] = items if items else None
            continue
        current[name] = _scalar(rest)
    for entry in entries:
        entry.pop("__indent__", None)
    return entries


# --------------------------------------------------------------------------- roster


@dataclass
class Roster:
    path: Path | None
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, str]] = field(default_factory=list)
    placeholder_rows: int = 0

    def contains(self, identity: str) -> bool:
        wanted = identity.strip().lstrip("@").lower()
        local = wanted.split("@", 1)[0] if wanted.endswith("@apache.org") else None
        for row in self.rows:
            for column, value in row.items():
                cell = value.strip().strip("`").lstrip("@").lower()
                if not cell:
                    continue
                if "email" in column and cell == wanted:
                    return True
                if ("apache" in column or column == "id") and cell in {wanted, local}:
                    return True
                if ("github" in column or "handle" in column) and cell == wanted:
                    return True
        return False


def parse_roster(path: Path | None) -> Roster | None:
    """The first markdown table whose header names an Apache ID, email or handle column."""
    text = read_text(path)
    if text is None:
        return None
    roster = Roster(path)
    header: list[str] | None = None
    for line, inside in _live_lines(text):
        stripped = line.strip()
        is_row = not inside and stripped.startswith("|")
        if header is not None and not is_row:
            break  # the roster table ended
        if not is_row:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if header is None:
            lowered = [c.lower() for c in cells]
            if any(("apache" in c or "email" in c or "handle" in c or "github" in c) for c in lowered):
                header = roster.columns = lowered
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue  # the |---|---| separator
        if all(("TODO" in c or not c.strip("`")) for c in cells):
            roster.placeholder_rows += 1
            continue
        roster.rows.append(dict(zip(header, cells, strict=False)))
    return roster


# --------------------------------------------------------------------------- user.md / project.md


def user_config_path(explicit: str | None, resolver: Resolver) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    elif os.environ.get("APACHE_MAGPIE_USER_CONFIG"):
        candidates.append(Path(os.environ["APACHE_MAGPIE_USER_CONFIG"]))
    else:
        candidates.append(Path.home() / ".config" / "apache-magpie" / "user.md")
        found = resolver.find("user.md")
        if found is not None:
            candidates.append(found)
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def dotted_value(text: str | None, dotted: str) -> str | None:
    """`a.b` from a table row, a flat `a.b: v` line, or a nested `a:` / `  b: v` block."""
    if not text:
        return None
    table = table_values(text)
    if isinstance(table.get(dotted), str):
        return str(table[dotted])
    flat = re.search(rf"^\s*-?\s*`?{re.escape(dotted)}`?\s*[:=][ \t]*(.+)$", text, re.MULTILINE)
    if flat and _clean(flat.group(1)):
        return _clean(flat.group(1))
    parts = dotted.split(".")
    if len(parts) == 2:
        block = re.search(rf"^(\s*){re.escape(parts[0])}:\s*$((?:\n\1\s+.*)+)", text, re.MULTILINE)
        if block:
            inner = re.search(rf"^\s+{re.escape(parts[1])}:[ \t]*(.+)$", block.group(2), re.MULTILINE)
            if inner and _clean(inner.group(1)):
                return _clean(inner.group(1))
    return None


def _clean(raw: str) -> str | None:
    value = _drop_comment(raw).strip().strip("`").strip("\"'").strip()
    return value or None


_DISABLED = {"null", "~", "false", "no", "none", "off"}


def nested_key_declared(text: str | None, parent: str, child: str) -> bool | None:
    """Whether `parent:` / `  child:` is declared in a YAML block of `text`, and to what.

    `None` when the key is absent; `False` for `null` / `~` / `false` / an empty
    value with nothing nested under it; `True` for any other value or a
    nested mapping. This is how an organization manifest's
    `release_process.automated_signing` says whether it offers the option.
    """
    if not text:
        return None
    lines = _strip_comments(text).splitlines()
    parent_indent: int | None = None
    for index, line in enumerate(lines):
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if parent_indent is None:
            if re.fullmatch(rf"\s*{re.escape(parent)}:\s*", _drop_comment(line)):
                parent_indent = indent
            continue
        if indent <= parent_indent or _FENCE.match(line):
            parent_indent = None
            if re.fullmatch(rf"\s*{re.escape(parent)}:\s*", _drop_comment(line)):
                parent_indent = indent
            continue
        match = re.fullmatch(rf"\s*{re.escape(child)}:(.*)", _drop_comment(line))
        if not match:
            continue
        value = match.group(1).strip()
        if value:
            return value.strip("\"'").lower() not in _DISABLED
        for following in lines[index + 1 :]:
            if not following.strip() or following.strip().startswith("#"):
                continue
            return len(following) - len(following.lstrip()) > indent and not _FENCE.match(following)
        return False
    return None


def organization(text: str | None) -> str:
    """`project.md` → `organization`, default `independent`."""
    if not text:
        return "independent"
    value = table_values(text).get("organization")
    if isinstance(value, str) and value and not is_placeholder(value):
        return value
    match = re.search(r"^\s*organization:\s*`?([A-Za-z][\w-]*)`?", text, re.MULTILINE)
    if match:
        return match.group(1)
    return "independent"
