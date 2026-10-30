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

"""The project's organization, read from its `project.md`.

The dashboard lists ASF PMCs only, so the bridge runs only for a project
whose `project.md` declares `organization: ASF`. The reading mirrors
`release_config.mdconfig.organization` (a `| organization | ... |` row,
else an `organization:` line; `independent` when neither is set), kept
here so the bridge depends on nothing else in the framework.
"""

from __future__ import annotations

import re
from pathlib import Path

DEFAULT = "independent"
_FENCE = re.compile(r"^\s*(```|~~~)")
# A value is a backticked token (an annotation may follow it, as in
# `ASF` (derived: apache/ GitHub org)) or, unquoted, the whole cell / rest of
# the line: never a prefix, so `ASF.example` is not `ASF`.
_ROW = re.compile(r"^\s*\|\s*`?organization`?\s*\|([^|]*)(?:\||$)")
_LINE = re.compile(r"^\s*organization:(.*)$")
_QUOTED = re.compile(r"^`([^`]*)`")


def _value(raw: str) -> str:
    raw = raw.strip()
    quoted = _QUOTED.match(raw)
    return (quoted.group(1) if quoted else raw).strip()


_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def organization(text: str) -> str:
    """`project.md` → `organization`; `independent` when unset or still a TODO."""
    inside = False
    line_value = None
    # A commented-out row is not configuration (release_config strips them too).
    for line in _COMMENT.sub("", text).splitlines():
        if _FENCE.match(line):
            inside = not inside
            continue
        if inside or line.lstrip().startswith(">"):
            continue
        row = _ROW.match(line)
        if row:
            value = _value(row.group(1))
            return DEFAULT if not value or value.startswith("TODO") else value
        if line_value is None and (match := _LINE.match(line)) and (value := _value(match.group(1))):
            line_value = value
    return line_value or DEFAULT


def read_organization(path: Path) -> str:
    """The organization `path` declares; raises `OSError` when it cannot be read."""
    return organization(path.read_text(encoding="utf-8"))
