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
"""A unified diff (`gh pr diff`) parsed into files, hunks and commentable lines.

GitHub accepts an inline review comment only on a line the diff shows. A
finding anchored at `file:line` is placed with `line` + `side` (RIGHT for an
added or context line of the new file, LEFT for a removed line); the legacy
`position` — lines below the file's first `@@` header, counting later hunk
headers — is kept for hosts that still require it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class DiffLine:
    kind: str  # "+", "-", " "
    text: str
    old: int | None
    new: int | None
    position: int


@dataclass
class DiffFile:
    path: str
    old_path: str | None
    is_new: bool = False
    is_deleted: bool = False
    is_binary: bool = False
    lines: list[DiffLine] = field(default_factory=list)

    @property
    def added(self) -> list[DiffLine]:
        return [line for line in self.lines if line.kind == "+"]

    def added_text(self) -> str:
        return "\n".join(line.text for line in self.added)

    def head(self, count: int = 20) -> list[str]:
        """The first added lines: a new file's header region."""
        return [line.text for line in self.added[:count]]


def parse(text: str) -> list[DiffFile]:
    """Every file section; tolerates excerpts that carry `---`/`+++` pairs without `diff --git` lines."""
    raws = text.splitlines()
    files: list[DiffFile] = []
    current: DiffFile | None = None
    old_no = new_no = position = 0
    in_hunk = False
    i = 0
    while i < len(raws):
        raw = raws[i]
        nxt = raws[i + 1] if i + 1 < len(raws) else ""
        i += 1
        if raw.startswith("diff --git "):
            match = re.match(r"diff --git a/(.*?) b/(.*)$", raw)
            current = DiffFile(
                path=match.group(2) if match else raw.split()[-1], old_path=match.group(1) if match else None
            )
            files.append(current)
            position, in_hunk = 0, False
            continue
        header_pair = raw.startswith("--- ") and nxt.startswith("+++ ")
        if header_pair and (current is None or in_hunk or current.lines):
            # An excerpt's next file section.
            target = nxt[4:].strip()
            current = DiffFile(path=_strip(target), old_path=_strip(raw[4:].strip()))
            current.is_new = raw[4:].strip() == "/dev/null"
            files.append(current)
            position, in_hunk = 0, False
            i += 1
            continue
        if current is None:
            continue
        if not in_hunk:
            if raw.startswith("new file mode"):
                current.is_new = True
            elif raw.startswith("deleted file mode"):
                current.is_deleted = True
            elif raw.startswith("Binary files") or raw.startswith("GIT binary patch"):
                current.is_binary = True
            elif raw.startswith("--- ") and raw[4:].strip() == "/dev/null":
                current.is_new = True
            elif raw.startswith("+++ "):
                target = raw[4:].strip()
                if target == "/dev/null":
                    current.is_deleted = True
                else:
                    current.path = _strip(target)
        hunk = _HUNK.match(raw)
        if hunk:
            if in_hunk:
                position += 1  # a later hunk header counts as a line
            in_hunk = True
            old_no, new_no = int(hunk.group(1)), int(hunk.group(3))
            continue
        if not in_hunk or raw.startswith("\\"):
            continue
        kind = raw[:1] if raw[:1] in "+- " else " "
        position += 1
        if kind == "+":
            current.lines.append(DiffLine("+", raw[1:], None, new_no, position))
            new_no += 1
        elif kind == "-":
            current.lines.append(DiffLine("-", raw[1:], old_no, None, position))
            old_no += 1
        else:
            current.lines.append(DiffLine(" ", raw[1:], old_no, new_no, position))
            old_no += 1
            new_no += 1
    return files


def _strip(target: str) -> str:
    return target[2:] if target.startswith(("a/", "b/")) else target


def by_path(files: list[DiffFile]) -> dict[str, DiffFile]:
    return {f.path: f for f in files}


def anchor(files: list[DiffFile], path: str, line: int, side: str = "RIGHT") -> dict[str, object] | None:
    """Where an inline comment on `path:line` goes, or None when the diff does not show that line."""
    found = by_path(files).get(path)
    if found is None:
        return None
    for entry in found.lines:
        if side == "RIGHT" and entry.new == line and entry.kind in "+ ":
            return {"path": path, "line": line, "side": "RIGHT", "position": entry.position}
        if side == "LEFT" and entry.old == line and entry.kind == "-":
            return {"path": path, "line": line, "side": "LEFT", "position": entry.position}
    return None
