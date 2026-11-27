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
"""Measure the always-on cost of an agent-instruction file.

An AGENTS.md (or CLAUDE.md, GEMINI.md, ...) is read whole into every session,
so every character in it is paid every time. This prints, per file:

- the total size in characters, lines and estimated tokens (characters / 4,
  the same estimate docs/mode-economics.md uses for always-on skill text);
- the files pulled in by ``@path`` import lines, which are always-on too;
- the generated table of contents (doctoc markers), which repeats the headings;
- the fenced code blocks;
- every ``##`` / ``###`` section, largest first.

Read-only. ``--json`` prints the same figures as JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Claude Code warns when a memory file passes this many characters.
HARNESS_WARN_CHARS = 40_000

TOC_START = re.compile(r"<!--\s*START doctoc", re.IGNORECASE)
TOC_END = re.compile(r"<!--\s*END doctoc", re.IGNORECASE)
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{2,3})\s+(.*\S)\s*$")
IMPORT = re.compile(r"^@(\S+)\s*$")


def tokens(chars: int) -> int:
    return round(chars / 4)


@dataclass
class Section:
    heading: str
    level: int
    line: int
    chars: int = 0
    lines: int = 0

    @property
    def tokens(self) -> int:
        return tokens(self.chars)


@dataclass
class Report:
    path: str
    chars: int
    lines: int
    tokens: int
    over_harness_warning: bool
    toc_chars: int = 0
    code_chars: int = 0
    code_blocks: int = 0
    imports: list[dict] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)


def measure(path: Path) -> Report:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    report = Report(
        path=str(path),
        chars=len(text),
        lines=len(lines),
        tokens=tokens(len(text)),
        over_harness_warning=len(text) > HARNESS_WARN_CHARS,
    )

    sections: list[Section] = []
    in_toc = in_fence = False
    for number, line in enumerate(lines, start=1):
        if not in_fence and TOC_START.search(line):
            in_toc = True
        if in_toc:
            report.toc_chars += len(line)
            if TOC_END.search(line):
                in_toc = False
            continue
        if FENCE.match(line):
            if not in_fence:
                report.code_blocks += 1
            in_fence = not in_fence
            report.code_chars += len(line)
        elif in_fence:
            report.code_chars += len(line)
        else:
            heading = HEADING.match(line)
            if heading:
                sections.append(Section(heading.group(2), len(heading.group(1)), number))
            imported = IMPORT.match(line)
            if imported:
                target = (path.parent / imported.group(1)).expanduser()
                size = target.stat().st_size if target.is_file() else None
                report.imports.append({"line": number, "path": imported.group(1), "chars": size})
        # Every line counts towards the innermost open section, the toc aside.
        if sections:
            sections[-1].chars += len(line)
            sections[-1].lines += 1

    report.sections = [
        {**asdict(s), "tokens": s.tokens} for s in sorted(sections, key=lambda s: s.chars, reverse=True)
    ]
    return report


def render(report: Report) -> str:
    out = [
        f"{report.path}: {report.chars:,} chars, {report.lines:,} lines, ~{report.tokens:,} tokens always-on"
    ]
    if report.over_harness_warning:
        out.append(f"  over the {HARNESS_WARN_CHARS:,}-char harness warning")
    imported = sum(i["chars"] or 0 for i in report.imports)
    for item in report.imports:
        size = "missing" if item["chars"] is None else f"{item['chars']:,} chars"
        out.append(f"  @import line {item['line']}: {item['path']} ({size})")
    if imported:
        out.append(f"  imports add ~{tokens(imported):,} tokens")
    if report.toc_chars:
        out.append(f"  generated TOC: ~{tokens(report.toc_chars):,} tokens")
    if report.code_blocks:
        out.append(f"  {report.code_blocks} code blocks: ~{tokens(report.code_chars):,} tokens")
    out.append("  sections, largest first (a ### is not counted again in its ##):")
    for s in report.sections:
        indent = "    " if s["level"] == 2 else "      "
        out.append(
            f"{indent}~{s['tokens']:>6,} tok {s['lines']:>4} lines  "
            f"L{s['line']:<5} {'#' * s['level']} {s['heading']}"
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)

    reports = []
    for path in args.files:
        if not path.is_file():
            print(f"error: {path} is not a file", file=sys.stderr)
            return 2
        reports.append(measure(path))

    if args.json:
        print(json.dumps([asdict(r) for r in reports], indent=2))
    else:
        print("\n\n".join(render(r) for r in reports))
        if len(reports) > 1:
            total = sum(r.tokens for r in reports)
            print(f"\nall files: ~{total:,} tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
