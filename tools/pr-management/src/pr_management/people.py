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
"""Who is a bot, who is a maintainer.

"Maintainer" is a member of `committers_team` or an account with `write` /
`maintain` / `admin` on the upstream repo. `authorAssociation` is only a first
filter: GitHub reports `COLLABORATOR` for triage- and read-role collaborators
too. A `COLLABORATOR`/`MEMBER`/`OWNER` login that is in neither the team roster
nor a permission read is *unknown*; the rule that meets one records it in
`Maintainers.unresolved`, decides as if it were a maintainer (the direction
that never talks over a maintainer), and the skill resolves the login and
classifies again.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .model import COLLABORATOR_ASSOCIATIONS

_KNOWN_BOTS = frozenset(
    {
        "dependabot",
        "dependabot[bot]",
        "renovate",
        "renovate[bot]",
        "github-actions",
        "github-actions[bot]",
    }
)

MAINTAINER_PERMISSIONS = frozenset({"write", "maintain", "admin"})


def is_bot(login: str) -> bool:
    lowered = login.lower()
    return lowered in _KNOWN_BOTS or lowered.endswith("[bot]")


def is_copilot(login: str) -> bool:
    return "copilot" in login.lower()


@dataclass
class Maintainers:
    team: frozenset[str] | None = None
    permissions: dict[str, str] = field(default_factory=dict)
    unresolved: set[str] = field(default_factory=set)

    def is_maintainer(self, login: str, association: str) -> bool:
        """Decide; an unknown login counts as a maintainer and is recorded."""
        if association not in COLLABORATOR_ASSOCIATIONS:
            return False
        key = login.lower()
        if self.team is not None and key in self.team:
            return True
        permission = self.permissions.get(key)
        if permission is not None:
            return permission in MAINTAINER_PERMISSIONS
        self.unresolved.add(login)
        return True

    def known(self, login: str) -> bool | None:
        """True / False when settled, None when a permission read is still needed."""
        key = login.lower()
        if self.team is not None and key in self.team:
            return True
        permission = self.permissions.get(key)
        return None if permission is None else permission in MAINTAINER_PERMISSIONS


def load_team(path: Path | None) -> frozenset[str] | None:
    """`team-members` output: one login per line."""
    if path is None:
        return None
    return frozenset(
        line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def load_permissions(paths: list[Path]) -> dict[str, str]:
    """`upstream-permission` saves, one per login, named `permission-<login>`.

    The file holds the bare permission (`write`, `read`, …); the login is
    the file name's suffix, so one save per login needs no wrapper format.
    A JSON object `{"login": ..., "permission": ...}` is accepted as well.
    """
    found: dict[str, str] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8").strip()
        if text.startswith("{"):
            data = json.loads(text)
            found[str(data["login"]).lower()] = str(data["permission"]).strip().lower()
            continue
        login = path.name.removeprefix("permission-").removesuffix(".txt")
        found[login.lower()] = text.strip('"').lower()
    return found
