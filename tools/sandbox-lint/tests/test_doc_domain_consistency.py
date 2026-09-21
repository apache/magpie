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

"""The update skill's `allowedDomains` prose must match the dogfooded settings.

`setup-isolated-setup-update` tells the agent which sandbox domains are a
current default and which were deliberately dropped. When
`.claude/settings.json` moves and that prose does not, the skill reports the
absence of a removed host as drift and walks adopters into re-adding dead
allowlist entries. These tests read both sides and fail on that divergence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
SKILL = REPO_ROOT / "plugins" / "magpie-setup" / "skills" / "isolated-setup-update" / "SKILL.md"

# The two prose anchors the assertions parse. Rewording the bullet is fine;
# keeping these phrases is what makes the claim machine-checkable.
KEPT_RE = re.compile(r"default allows (.+?), the\s+only hosts", re.DOTALL)
DROPPED_RE = re.compile(r"once sat beside them\s*\((.+?)\) were dropped", re.DOTALL)


def _backticked(blob: str) -> set[str]:
    return set(re.findall(r"`([^`]+)`", blob))


def _settings_domains() -> set[str]:
    settings = json.loads(SETTINGS.read_text())
    return set(settings["sandbox"]["network"]["allowedDomains"])


def _skill_text() -> str:
    return SKILL.read_text()


def test_kept_domains_are_actually_allowed() -> None:
    match = KEPT_RE.search(_skill_text())
    assert match, "the skill no longer states which domains the default allows"
    kept = _backticked(match.group(1))
    assert kept, "no domains parsed out of the 'default allows' sentence"
    assert kept <= _settings_domains(), (
        "the update skill names domains as the dogfooded default that "
        f"{SETTINGS} does not allow: {sorted(kept - _settings_domains())}"
    )


def test_dropped_domains_are_not_allowed_again() -> None:
    match = DROPPED_RE.search(_skill_text())
    assert match, "the skill no longer lists the dropped link-target hosts"
    dropped = _backticked(match.group(1))
    assert dropped, "no domains parsed out of the dropped-hosts list"
    readded = dropped & _settings_domains()
    assert not readded, (
        f"the update skill says these hosts were dropped, but {SETTINGS} allows them again: {sorted(readded)}"
    )
