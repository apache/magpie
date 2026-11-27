#!/usr/bin/env python3
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
#
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Find subtree-only sections of an AGENTS.md and move them into nested files.

``suggest FILE`` lists every ``##`` / ``###`` section whose path references
(inline code and relative links that exist on disk) all sit under one
subdirectory: the candidates for a nested ``<dir>/AGENTS.md``. Read-only.

``apply FILE --section HEADING --dir DIR`` moves one section there:

- creates ``DIR/AGENTS.md`` when it is missing, with the root file's leading
  licence comment, a title, and one line saying the root file still governs;
  otherwise appends to it;
- moves the section's text byte-identical, except that its heading level is
  raised to ``##`` when it was deeper and every relative link is rewritten to
  reach the same target from the new directory;
- in the root, removes the section, or, when other files link to its anchor
  (or ``--pointer`` is given), keeps the heading with one line pointing at the
  nested file, so those links still land;
- mirrors the root's ``CLAUDE.md -> AGENTS.md`` symlink in ``DIR`` when the root
  has one.

``--dry-run`` prints the plan without writing anything; the skill shows it as
the proposal. Prove the move afterwards with ``rule_inventory.py --also
DIR/AGENTS.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
INLINE_CODE = re.compile(r"`([^`\s]+)`")
LINK = re.compile(r"(\]\()([^)\s]+)(\))")
LEADING_COMMENT = re.compile(r"\A\s*(<!--(?:(?!doctoc).)*?-->[ \t]*\n)", re.DOTALL)
SKIP_DIRS = {".git", "node_modules", ".apache-magpie", ".venv"}


def slug(heading: str) -> str:
    """GitHub's anchor for a heading."""
    text = re.sub(r"[^\w\- ]", "", heading.lower().replace("`", ""))
    return text.replace(" ", "-")


@dataclass
class Section:
    heading: str
    level: int
    start: int  # index of the heading line
    end: int  # index one past the last line

    def lines(self, lines: list[str]) -> list[str]:
        return lines[self.start : self.end]


def sections(lines: list[str]) -> list[Section]:
    found: list[Section] = []
    in_fence = False
    for index, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        heading = None if in_fence else HEADING.match(line)
        if heading and len(heading.group(1)) >= 2:
            found.append(Section(heading.group(2), len(heading.group(1)), index, len(lines)))
    for i, section in enumerate(found):
        for later in found[i + 1 :]:
            if later.level <= section.level:
                section.end = later.start
                break
    return found


def is_relative(target: str) -> bool:
    return not (re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith(("/", "#")))


def references(body: str, base: Path) -> list[Path]:
    """Existing paths the section names, as inline code or relative links.

    A Markdown file is named to be read ("see this"), not as evidence that the
    section governs its directory, so it does not count.
    """
    candidates = [*INLINE_CODE.findall(body), *(m.group(2) for m in LINK.finditer(body))]
    found: list[Path] = []
    for raw in candidates:
        target = raw.split("#", 1)[0].rstrip("/")
        if not target or not is_relative(target) or "<" in target or "*" in target or target.endswith(".md"):
            continue
        path = (base / target).resolve()
        if path.exists() and path not in found:
            found.append(path)
    return found


def common_dir(paths: list[Path], root: Path) -> Path | None:
    """The deepest directory below ``root`` holding every path, if there is one."""
    dirs = [p if p.is_dir() else p.parent for p in paths]
    common = Path(os.path.commonpath([str(d) for d in dirs]))
    if common == root or root not in common.parents:
        return None
    return common


def suggest(file: Path, min_refs: int) -> list[dict]:
    lines = file.read_text(encoding="utf-8").splitlines(keepends=True)
    root = file.parent.resolve()
    out = []
    for section in sections(lines):
        body = "".join(section.lines(lines)[1:])
        refs = references(body, root)
        if len(refs) < min_refs:
            continue
        directory = common_dir(refs, root)
        if directory is None:
            continue
        out.append(
            {
                "heading": section.heading,
                "line": section.start + 1,
                "tokens": round(len(body) / 4),
                "dir": str(directory.relative_to(root)),
                "references": [str(p.relative_to(root)) for p in refs],
                "nested_exists": (directory / file.name).is_file(),
            }
        )
    return out


def rewrite_links(text: str, old_base: Path, new_base: Path, root_file: Path, local: set[str]) -> str:
    def fix(match: re.Match[str]) -> str:
        target = match.group(2)
        if target.startswith("#"):
            if target[1:] in local:
                return match.group(0)
            new = os.path.relpath(root_file, new_base) + target
        elif is_relative(target):
            path, _, anchor = target.partition("#")
            new = os.path.relpath((old_base / path).resolve(), new_base)
            new += f"#{anchor}" if anchor else ""
        else:
            return match.group(0)
        return f"{match.group(1)}{new}{match.group(3)}"

    out = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if FENCE.match(line):
            in_fence = not in_fence
        out.append(line if in_fence else LINK.sub(fix, line))
    return "".join(out)


def inbound_links(file: Path, anchor: str) -> list[str]:
    root = file.parent.resolve()
    pattern = re.compile(re.escape(file.name) + "#" + re.escape(anchor) + r"\b")
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            path = Path(dirpath) / name
            try:
                if pattern.search(path.read_text(encoding="utf-8")):
                    hits.append(str(path.relative_to(root)))
            except (OSError, UnicodeDecodeError):
                continue
    return hits


def apply(file: Path, heading: str, directory: str, pointer: bool, dry_run: bool) -> dict:
    root_file = file.resolve()
    root = root_file.parent
    lines = root_file.read_text(encoding="utf-8").splitlines(keepends=True)
    matches = [s for s in sections(lines) if s.heading == heading]
    if len(matches) != 1:
        raise SystemExit(f"error: {len(matches)} sections are headed {heading!r}; need exactly one")
    section = matches[0]
    target_dir = (root / directory).resolve()
    if not target_dir.is_dir() or root not in target_dir.parents:
        raise SystemExit(f"error: {directory!r} is not a subdirectory of {root}")
    nested = target_dir / root_file.name

    moved = section.lines(lines)
    shift = section.level - 2
    local = set()
    for i, line in enumerate(moved):
        match = HEADING.match(line)
        if match:
            local.add(slug(match.group(2)))
            if shift > 0:
                moved[i] = "#" * (len(match.group(1)) - shift) + line[len(match.group(1)) :]
    body = rewrite_links("".join(moved), root, target_dir, root_file, local)

    if nested.is_file():
        existing = nested.read_text(encoding="utf-8")
        new_nested = existing.rstrip("\n") + "\n\n" + body
    else:
        header = LEADING_COMMENT.match(root_file.read_text(encoding="utf-8"))
        back = os.path.relpath(root_file, target_dir)
        new_nested = (
            (header.group(1) + "\n" if header else "")
            + f"# AGENTS — conventions for `{directory.rstrip('/')}/`\n\n"
            + f"Loaded in addition to the repository-wide [`{root_file.name}`]({back}), "
            + "which still governs everything here.\n\n"
            + body
        )

    anchor = slug(heading)
    inbound = [h for h in inbound_links(root_file, anchor) if (root / h).resolve() != root_file]
    keep_heading = pointer or bool(inbound)
    rel_nested = os.path.relpath(nested, root)
    replacement = []
    if keep_heading:
        replacement = [
            lines[section.start],
            "\n",
            f"When working under `{directory.rstrip('/')}/`, read "
            f"[`{rel_nested}`]({rel_nested}#{slug(heading)}).\n",
            "\n",
        ]
    new_root = lines[: section.start] + replacement + lines[section.end :]

    claude_link = root / "CLAUDE.md"
    mirror = (
        claude_link.is_symlink()
        and os.readlink(claude_link) == root_file.name
        and not (target_dir / "CLAUDE.md").exists()
    )

    plan = {
        "section": heading,
        "moved_lines": len(moved),
        "moved_tokens": round(len(body) / 4),
        "nested_file": rel_nested,
        "nested_created": not nested.is_file(),
        "heading_shift": max(shift, 0),
        "root_keeps_pointer": keep_heading,
        "inbound_links": inbound,
        "claude_symlink": mirror,
        "dry_run": dry_run,
    }
    if not dry_run:
        nested.write_text(new_nested, encoding="utf-8")
        root_file.write_text("".join(new_root), encoding="utf-8")
        if mirror:
            (target_dir / "CLAUDE.md").symlink_to(root_file.name)
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("suggest", help="list subtree-only sections (read-only)")
    s.add_argument("file", type=Path)
    s.add_argument("--min-refs", type=int, default=2, help="path references a section needs (default 2)")
    a = sub.add_parser("apply", help="move one section into <dir>/AGENTS.md")
    a.add_argument("file", type=Path)
    a.add_argument("--section", required=True, help="the heading text, without the #s")
    a.add_argument("--dir", required=True, help="the subdirectory, relative to the file")
    a.add_argument(
        "--pointer", action="store_true", help="keep a pointer in the root even without inbound links"
    )
    a.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args(argv)

    if not args.file.is_file():
        print(f"error: {args.file} is not a file", file=sys.stderr)
        return 2
    if args.command == "suggest":
        print(json.dumps(suggest(args.file, args.min_refs), indent=2))
    else:
        print(json.dumps(apply(args.file, args.section, args.dir, args.pointer, args.dry_run), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
