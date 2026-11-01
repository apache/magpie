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
"""`CODEOWNERS`: parse, match a path (the last matching rule wins), resolve team ownership.

Team ownership is membership of the named team — read with `team-members
<slug>` — not membership of the organisation, which is what the old
`orgs/<org>/members/<viewer>` probe tested.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    pattern: str
    owners: tuple[str, ...]
    regex: re.Pattern[str]


def _compile(pattern: str) -> re.Pattern[str]:
    """GitHub's CODEOWNERS glob, as a regex over a repository-relative path."""
    anchored = pattern.startswith("/")
    body = pattern.strip("/") if pattern != "/" else ""
    directory = pattern.endswith("/")
    out = ""
    i = 0
    while i < len(body):
        char = body[i]
        if body.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if body.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if char == "*":
            out += "[^/]*"
        elif char == "?":
            out += "[^/]"
        else:
            out += re.escape(char)
        i += 1
    if not anchored and "/" not in body:
        out = "(?:.*/)?" + out  # a bare name matches at any depth
    tail = "/.*" if directory else "(?:/.*)?"
    return re.compile("^" + out + tail + "$")


def parse(text: str | None) -> list[Rule]:
    rules: list[Rule] = []
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        rules.append(
            Rule(parts[0], tuple(p for p in parts[1:] if p.startswith("@") or "@" in p), _compile(parts[0]))
        )
    return rules


def owners_of(rules: list[Rule], path: str) -> tuple[str, ...]:
    """The owners of `path`: the last matching rule's, which may be none."""
    found: tuple[str, ...] = ()
    for rule in rules:
        if rule.regex.match(path):
            found = rule.owners
    return found


def teams(rules: list[Rule]) -> list[str]:
    """Every `@org/team` the file names, as `org/team`."""
    seen: list[str] = []
    for rule in rules:
        for owner in rule.owners:
            name = owner.lstrip("@")
            if "/" in name and name not in seen:
                seen.append(name)
    return seen


def owns(owners: tuple[str, ...], viewer: str, viewer_teams: set[str]) -> bool:
    for owner in owners:
        name = owner.lstrip("@").lower()
        if name == viewer.lower() or name in viewer_teams:
            return True
    return False
