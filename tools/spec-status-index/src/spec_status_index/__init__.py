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

"""Print spec-loop specs grouped by status.

Reads YAML frontmatter from tools/spec-loop/specs/*.md and prints a
table grouped by status.  ``--ready`` filters to actionable specs
(status: proposed or experimental) so build iterations can choose
the next work item mechanically.

Run from repo root:
    uv run --project tools/spec-status-index spec-status
    uv run --project tools/spec-status-index spec-status --ready
    uv run --project tools/spec-status-index spec-status --status proposed
    uv run --project tools/spec-status-index spec-status --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPECS_DIR = Path("tools/spec-loop/specs")

KNOWN_STATUSES = ("stable", "experimental", "proposed", "off")

# Specs that are ready to be picked up for build iterations.
READY_STATUSES = frozenset({"proposed", "experimental"})

# Files without standard spec frontmatter that are skipped.
SKIP_FILES = frozenset({"README.md", "overview.md"})

# Display order for statuses.
STATUS_ORDER = {"proposed": 0, "experimental": 1, "stable": 2, "off": 3}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SpecEntry:
    file: Path
    title: str
    status: str
    kind: str
    mode: str


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_FIELD_RE = re.compile(r"^(\w+)\s*:\s*(.+)$", re.MULTILINE)
# Specs may open with leading HTML comments (e.g. the SPDX licence header)
# before the `---` frontmatter block; strip them so the delimiter can start.
_LEADING_COMMENTS_RE = re.compile(r"^\s*(?:<!--.*?-->\s*)+", re.DOTALL)


def _strip_comment(value: str) -> str:
    """Drop a YAML inline comment from a single-line scalar.

    YAML starts a comment at ``#`` only when it opens the value or follows
    whitespace, and never inside a quoted scalar, so ``title: C# bindings``
    and ``title: "a # b"`` keep their text.  The spec template introduces
    every index field with one (``status: experimental   # stable | ...``),
    and without this the comment becomes part of the value.
    """
    quote = ""
    for index, char in enumerate(value):
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value


def parse_frontmatter(text: str) -> dict[str, str]:
    """Return a flat dict of scalar frontmatter fields.

    Block scalars (``>``, ``|``) and multi-line values are omitted —
    only single-line key: value pairs are captured, which is all that
    spec frontmatter uses for the index fields (title, status, kind, mode).
    """
    m = _FM_RE.match(_LEADING_COMMENTS_RE.sub("", text, count=1))
    if not m:
        return {}
    block = m.group(1)
    result: dict[str, str] = {}
    for key, val in _FIELD_RE.findall(block):
        result[key] = _strip_comment(val.strip())
    return result


def find_repo_root(start: Path) -> Path:
    p = start.resolve()
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    raise RuntimeError(f"Could not find repo root (.git) from {start}")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_specs(specs_dir: Path) -> list[SpecEntry]:
    """Return SpecEntry list sorted by status priority then title."""
    entries: list[SpecEntry] = []
    for md_file in sorted(specs_dir.glob("*.md")):
        if md_file.name in SKIP_FILES:
            continue
        text = md_file.read_text()
        fm = parse_frontmatter(text)
        if not fm.get("status"):
            continue
        entries.append(
            SpecEntry(
                file=md_file,
                title=fm.get("title", md_file.stem),
                status=fm.get("status", "unknown"),
                kind=fm.get("kind", ""),
                mode=fm.get("mode", ""),
            )
        )
    entries.sort(key=lambda e: (STATUS_ORDER.get(e.status, 99), e.title.lower()))
    return entries


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _col_widths(entries: list[SpecEntry]) -> tuple[int, int, int, int]:
    title_w = max((len(e.title) for e in entries), default=5)
    status_w = max((len(e.status) for e in entries), default=6)
    kind_w = max((len(e.kind) for e in entries), default=4)
    mode_w = max((len(e.mode) for e in entries), default=4)
    return (
        max(title_w, 5),
        max(status_w, 6),
        max(kind_w, 4),
        max(mode_w, 4),
    )


def format_table(entries: list[SpecEntry]) -> str:
    if not entries:
        return "(no specs matched)\n"

    tw, sw, kw, mw = _col_widths(entries)
    header = f"{'Title':<{tw}}  {'Status':<{sw}}  {'Kind':<{kw}}  {'Mode':<{mw}}  File"
    sep = "-" * len(header)

    lines = [header, sep]
    current_status = ""
    for e in entries:
        if e.status != current_status:
            if current_status:
                lines.append("")
            current_status = e.status
        lines.append(f"{e.title:<{tw}}  {e.status:<{sw}}  {e.kind:<{kw}}  {e.mode:<{mw}}  {e.file.name}")
    lines.append("")
    return "\n".join(lines)


def format_json(entries: list[SpecEntry]) -> str:
    return json.dumps(
        [
            {
                "title": e.title,
                "status": e.status,
                "kind": e.kind,
                "mode": e.mode,
                "file": e.file.name,
            }
            for e in entries
        ],
        indent=2,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Print spec-loop specs by status. "
            "Use --ready to filter to actionable items (proposed + experimental)."
        )
    )
    parser.add_argument(
        "--ready",
        action="store_true",
        help="Show only specs with status 'proposed' or 'experimental'.",
    )
    parser.add_argument(
        "--status",
        metavar="STATUS",
        help=f"Filter to a specific status. One of: {', '.join(KNOWN_STATUSES)}.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit JSON instead of a text table.",
    )
    parser.add_argument(
        "--specs-dir",
        type=Path,
        default=None,
        help="Override path to the specs directory (default: tools/spec-loop/specs relative to repo root).",
    )
    args = parser.parse_args()

    try:
        repo_root = find_repo_root(Path.cwd())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    specs_dir = args.specs_dir if args.specs_dir else repo_root / SPECS_DIR
    if not specs_dir.is_dir():
        print(f"error: specs directory not found: {specs_dir}", file=sys.stderr)
        sys.exit(1)

    entries = load_specs(specs_dir)

    if args.ready and args.status:
        print("error: --ready and --status are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    if args.ready:
        entries = [e for e in entries if e.status in READY_STATUSES]
    elif args.status:
        if args.status not in KNOWN_STATUSES:
            print(
                f"error: unknown status {args.status!r}. Known: {', '.join(KNOWN_STATUSES)}",
                file=sys.stderr,
            )
            sys.exit(1)
        entries = [e for e in entries if e.status == args.status]

    if args.as_json:
        print(format_json(entries))
    else:
        print(format_table(entries), end="")


if __name__ == "__main__":
    main()
