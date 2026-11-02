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
"""Read the tables and sections of the adopter's markdown config.

The config files are prose documents with `| key | value |` tables. Rows inside
code fences, blockquotes and HTML comments are examples, never values.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .layers import config_layers

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_BACKTICK = re.compile(r"`([^`]+)`")


@dataclass
class Resolver:
    """Find `<project-config>` files, personal layer first."""

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

    def read(self, name: str) -> str | None:
        path = self.find(name)
        if path is None:
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None


def live_lines(text: str) -> Iterator[tuple[str, bool]]:
    """(line, inside_fence) for every line, with HTML comments removed."""
    inside = False
    for line in re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).splitlines():
        if _FENCE.match(line):
            inside = not inside
            yield line, True
            continue
        yield line, inside


def table_rows(text: str | None) -> Iterator[list[str]]:
    """The cells of every live table row, header and separator rows excluded."""
    if not text:
        return
    for line, inside in live_lines(text):
        stripped = line.strip()
        if inside or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        yield cells


def first_token(cell: str) -> str | None:
    """A cell's value: its first backticked token when it opens with one, else its text.

    `*(…)*` / `_(…)_` notes and empty cells mean unset.
    """
    cell = cell.strip()
    if not cell or cell.startswith(("*(", "_(")) or cell in {"—", "-"}:
        return None
    if cell.startswith("`"):
        match = _BACKTICK.match(cell)
        return match.group(1).strip() if match else None
    return cell


def tokens(cell: str) -> list[str]:
    """Every backticked token in a cell, in order."""
    return [t.strip() for t in _BACKTICK.findall(cell)]


def key_values(text: str | None, column: int = 1) -> dict[str, str | None]:
    """`` | `key` | value | `` rows; the first row for a key wins."""
    values: dict[str, str | None] = {}
    for cells in table_rows(text):
        if len(cells) <= column:
            continue
        match = re.fullmatch(r"`([^`]+)`", cells[0])
        if not match or match.group(1) in values:
            continue
        values[match.group(1)] = first_token(cells[column])
    return values


def section(text: str | None, title: str) -> str | None:
    """The text under the first heading containing `title`, to the next heading of its level or higher."""
    if not text:
        return None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        match = _HEADING.match(line)
        if not match or title.lower() not in match.group(2).lower():
            continue
        level = len(match.group(1))
        body: list[str] = []
        inside = False
        for later in lines[i + 1 :]:
            if _FENCE.match(later):
                inside = not inside
            heading = None if inside else _HEADING.match(later)
            if heading and len(heading.group(1)) <= level:
                break
            body.append(later)
        return "\n".join(body)
    return None


def first_fence(text: str | None) -> str | None:
    """The body of the first fenced block in `text`."""
    if not text:
        return None
    body: list[str] = []
    inside = False
    for line in text.splitlines():
        if _FENCE.match(line):
            if inside:
                return "\n".join(body)
            inside = True
            continue
        if inside:
            body.append(line)
    return None
