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
"""
Refuse a relative Markdown link that goes through a symlinked directory.

GitHub's web view does not follow a directory symlink, so a link such as
``skills/<name>/SKILL.md`` (``skills/<name>`` links into
``plugins/magpie-<family>/skills/``) returns 404 there, while local readers,
agents and lychee, which all resolve symlinks, follow it fine (#2330). Each
link's path is walked one component at a time, and any component that is a
symlink to a directory is reported, whatever the directory is called, so a
future symlink layer is caught too.

Checks inline links and images (``[text](path)``), reference definitions
(``[id]: path``) and ``href`` / ``src`` attributes. Links inside fenced code
blocks and inline code spans are not links. External URLs, absolute paths,
bare ``#anchors``, and targets that do not exist (lychee reports those) are
skipped.

With ``--fix``, each such link is rewritten to the real path, relative to the
file, keeping its ``#fragment``.

Usage: ``check-symlink-links.py [--fix] FILE...`` (prek passes the files).
Exits 1 when a link goes through a symlinked directory and ``--fix`` is off.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[2]

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
# [text](target "title") and ![alt](target); the target may be wrapped in <>.
_INLINE = re.compile(r"\]\(\s*(<[^>\n]*>|[^)\s]+)")
_REFERENCE = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*(<[^>\n]*>|\S+)")
_ATTRIBUTE = re.compile(r"""\b(?:href|src)\s*=\s*["']([^"'\n]+)["']""")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


@dataclass(frozen=True)
class Finding:
    """One link through a symlinked directory."""

    file: Path
    line: int
    target: str
    symlink: str
    fixed: str | None


def _links(line: str) -> Iterator[tuple[int, int, str]]:
    """``(start, end, target)`` of every link target on one line outside code spans."""
    masked = _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)
    for pattern in (_INLINE, _REFERENCE, _ATTRIBUTE):
        for match in pattern.finditer(masked):
            start, end = match.span(1)
            yield start, end, line[start:end]


def _split(target: str) -> tuple[str, str]:
    """A link target as ``(path, suffix)``, the suffix being ``?query`` and/or ``#fragment``."""
    cut = min((i for i in (target.find("#"), target.find("?")) if i >= 0), default=len(target))
    return target[:cut], target[cut:]


def _symlinked_dir(path: Path, root: Path) -> Path | None:
    """The first component of ``path`` (relative to ``root``) that is a symlink to a directory."""
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink() and current.is_dir():
            return current
    return None


def check_text(text: str, file: Path, root: Path = REPO_ROOT) -> tuple[list[Finding], str]:
    """The findings in one file's text, and the text with each of them fixed."""
    findings: list[Finding] = []
    out: list[str] = []
    fence: str | None = None
    base = file.parent
    for number, line in enumerate(text.splitlines(keepends=True), start=1):
        opener = _FENCE.match(line)
        if fence is not None:
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                fence = None
            out.append(line)
            continue
        if opener:
            fence = opener.group(1)
            out.append(line)
            continue
        edits: list[tuple[int, int, str]] = []
        for start, end, raw in _links(line):
            target = raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw
            path, suffix = _split(target)
            if not path or path.startswith("/") or _SCHEME.match(path):
                continue
            absolute = Path(os.path.normpath(base / unquote(path)))
            try:
                relative = absolute.relative_to(root)
            except ValueError:
                continue  # outside the repository
            if not absolute.exists():
                continue  # a broken link is lychee's to report
            link = _symlinked_dir(relative, root)
            if link is None:
                continue
            real = os.path.relpath(absolute.resolve(), base.resolve())
            if path.endswith("/") and not real.endswith("/"):
                real += "/"
            fixed = real + suffix
            findings.append(Finding(file, number, target, str(link.relative_to(root)), fixed))
            replacement = f"<{fixed}>" if raw.startswith("<") else fixed
            edits.append((start, end, replacement))
        for start, end, replacement in sorted(edits, reverse=True):
            line = line[:start] + replacement + line[end:]
        out.append(line)
    return findings, "".join(out)


def main(argv: Sequence[str] | None = None, root: Path = REPO_ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--fix", action="store_true", help="rewrite each link to its real path")
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args(argv)
    total = 0
    for name in args.files:
        file = Path(os.path.abspath(name))
        if file.suffix != ".md" or not file.is_file():
            continue
        text = file.read_text(encoding="utf-8")
        findings, fixed = check_text(text, file, root)
        if not findings:
            continue
        total += len(findings)
        if args.fix:
            file.write_text(fixed, encoding="utf-8")
            continue
        for f in findings:
            shown = os.path.relpath(f.file, Path.cwd())
            print(
                f"{shown}:{f.line}: `{f.target}` goes through the symlinked directory `{f.symlink}`, "
                f"which GitHub's web view does not follow; link `{f.fixed}` instead"
            )
    if total and not args.fix:
        print(
            f"\n{total} link(s) go through a symlinked directory. "
            "Run `python3 tools/dev/check-symlink-links.py --fix <files>` to rewrite them (#2330).",
            file=sys.stderr,
        )
        return 1
    if total:
        print(f"rewrote {total} link(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
