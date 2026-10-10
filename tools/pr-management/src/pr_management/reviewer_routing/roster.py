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
"""The reviewer roster: `reviewer-roster.md`, else the area rotations in `release-trains.md`.

`reviewer-roster.md` is the YAML-shaped list the template documents
(`- handle:` / `areas:` / `max_reviews:`), read outside HTML comments.
`release-trains.md` has no fixed area shape, so two are read: a table whose
header names a handle column and an area/component column, and bullets of
the form `- <area> — @handle, @handle` under *Known release-manager
rotations*. A handle starting with `TODO` is a template placeholder and is
skipped. When both files exist, `reviewer-roster.md` wins per handle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import mdconfig

DEFAULT_MAX_REVIEWS = 5
_HANDLE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


@dataclass
class Member:
    handle: str
    areas: list[str] = field(default_factory=list)
    max_reviews: int = DEFAULT_MAX_REVIEWS


@dataclass
class Roster:
    source: str | None
    members: list[Member]
    files: dict[str, str | None]


def _valid(handle: str) -> bool:
    return bool(_HANDLE.match(handle)) and not handle.upper().startswith("TODO")


def parse_reviewer_roster(text: str) -> list[Member]:
    members: list[Member] = []
    current: Member | None = None
    in_areas = False
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    for line, inside in mdconfig.live_lines(body):
        if inside:
            continue
        handle = re.match(r"^\s*-\s+handle:\s*@?([^\s#]+)", line)
        if handle:
            current = Member(handle.group(1))
            members.append(current)
            in_areas = False
            continue
        if current is None:
            continue
        if re.match(r"^\s+areas:\s*$", line):
            in_areas = True
            continue
        inline = re.match(r"^\s+areas:\s*\[(.*)\]\s*$", line)
        if inline:
            current.areas.extend(a.strip().strip("'\"") for a in inline.group(1).split(",") if a.strip())
            in_areas = False
            continue
        limit = re.match(r"^\s+max_reviews:\s*(\d+)", line)
        if limit:
            current.max_reviews = int(limit.group(1))
            in_areas = False
            continue
        item = re.match(r"^\s+-\s+([^#]+?)\s*(?:#.*)?$", line)
        if in_areas and item:
            current.areas.append(item.group(1).strip().strip("'\""))
            continue
        if line.strip() and not line.startswith(" "):
            current = None
            in_areas = False
    return [m for m in members if _valid(m.handle)]


def parse_release_trains(text: str) -> list[Member]:
    found: dict[str, Member] = {}
    header: list[str] | None = None
    for cells in mdconfig.table_rows(text):
        lowered = [c.lower() for c in cells]
        if (
            any(w in " ".join(lowered) for w in ("handle", "github", "login"))
            and any(w in " ".join(lowered) for w in ("area", "component"))
            and header is None
        ):
            header = lowered
            continue
        if header is None or len(cells) != len(header):
            continue
        h_col = next(i for i, c in enumerate(header) if any(w in c for w in ("handle", "github", "login")))
        a_col = next(i for i, c in enumerate(header) if any(w in c for w in ("area", "component")))
        area = cells[a_col].strip("` ")
        for handle in re.findall(r"@?([A-Za-z0-9][A-Za-z0-9-]{0,38})", cells[h_col]):
            if _valid(handle):
                found.setdefault(handle.lower(), Member(handle)).areas.append(area)
    rotations = mdconfig.section(text, "Known release-manager rotations") or ""
    for line, inside in mdconfig.live_lines(rotations):
        match = re.match(r"^\s*[-*]\s+\**`?([^`*—:-]+?)`?\**\s*[—:-]+\s*(.*)$", line)
        if inside or not match or line.lstrip().startswith(">"):
            continue
        area = match.group(1).strip()
        for handle in re.findall(r"@([A-Za-z0-9][A-Za-z0-9-]{0,38})", match.group(2)):
            if _valid(handle):
                found.setdefault(handle.lower(), Member(handle)).areas.append(area)
    return list(found.values())


def load(project_root: Path, config_dir: Path | None = None) -> Roster:
    resolver = mdconfig.Resolver(project_root, config_dir)
    files: dict[str, str | None] = {}
    members: dict[str, Member] = {}
    source: str | None = None
    trains = resolver.find("release-trains.md")
    files["release-trains.md"] = str(trains) if trains else None
    if trains is not None:
        for m in parse_release_trains(resolver.read("release-trains.md") or ""):
            members[m.handle.lower()] = m
        source = "release-trains"
    roster = resolver.find("reviewer-roster.md")
    files["reviewer-roster.md"] = str(roster) if roster else None
    if roster is not None:
        for m in parse_reviewer_roster(resolver.read("reviewer-roster.md") or ""):
            members[m.handle.lower()] = m
        source = "reviewer-roster"
    return Roster(
        source=source, members=sorted(members.values(), key=lambda m: m.handle.lower()), files=files
    )
