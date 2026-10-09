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

"""Tests for ``bump-hook-npm-pins.py``.

What matters is that a bump never lands a release still inside its cooldown,
never picks a pre-release, never moves a pin backwards, and touches only the
quoted ``<package>@<X.Y.Z>`` pins in ``additional_dependencies``. The registry
is replaced by a fake, so nothing here touches the network.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "bump-hook-npm-pins.py"

NOW = dt.datetime(2026, 10, 9, 6, 0, tzinfo=dt.UTC)

CONFIG = """\
repos:
  - repo: local
    hooks:
      - id: lychee
        additional_dependencies: ["cli:lychee"]
      - id: check-claude-mods
        language: node
        # "@anthropic-ai/claude-code@1.0.0" in a comment is not a pin
        additional_dependencies: ["@anthropic-ai/claude-code@2.1.288"]
      - id: other
        additional_dependencies: ["left-pad@1.0.0", "ranged@^2.0.0"]
"""

TIMES = {
    "@anthropic-ai/claude-code": {
        "created": "2025-01-01T00:00:00Z",
        "modified": "2026-10-08T18:22:58Z",
        "2.1.288": "2026-10-02T18:30:40Z",
        "2.1.292": "2026-10-06T17:10:31Z",
        "2.1.294": "2026-10-08T03:42:57Z",  # 26h old: past the 12-hour cooldown
        "2.1.295": "2026-10-08T18:22:58Z",  # 11.6h old: inside it
        "2.2.0-beta.1": "2026-10-01T00:00:00Z",  # pre-release: never picked
    },
    "left-pad": {
        "1.0.0": "2026-01-01T00:00:00Z",
        "1.1.0": "2026-10-05T00:00:00Z",  # 4 days old: inside the 7-day default
    },
}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bump_hook_npm_pins", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _load()


def test_finds_only_exact_pins_in_additional_dependencies(mod: ModuleType) -> None:
    assert mod.find_pins(CONFIG) == {
        "@anthropic-ai/claude-code": "2.1.288",
        "left-pad": "1.0.0",
    }


def test_bumps_to_newest_release_past_its_cooldown(mod: ModuleType) -> None:
    new, bumps = mod.bump(CONFIG, NOW, fetch=TIMES.__getitem__)
    assert bumps == [("@anthropic-ai/claude-code", "2.1.288", "2.1.294")]
    assert '"@anthropic-ai/claude-code@2.1.294"' in new
    # The comment and every other line are untouched.
    assert '"@anthropic-ai/claude-code@1.0.0" in a comment' in new
    assert '"left-pad@1.0.0"' in new


def test_default_cooldown_holds_back_a_recent_release(mod: ModuleType) -> None:
    later = NOW + dt.timedelta(days=3)
    _, bumps = mod.bump(CONFIG, later, fetch=TIMES.__getitem__)
    assert ("left-pad", "1.0.0", "1.1.0") in bumps


def test_never_moves_a_pin_backwards(mod: ModuleType) -> None:
    ahead = CONFIG.replace("claude-code@2.1.288", "claude-code@2.1.295")
    new, bumps = mod.bump(ahead, NOW, fetch=TIMES.__getitem__)
    assert bumps == []
    assert new == ahead


def test_compares_versions_numerically(mod: ModuleType) -> None:
    times = {"2.1.9": "2026-01-01T00:00:00Z", "2.1.10": "2026-01-02T00:00:00Z"}
    assert mod.pick_version(times, NOW, dt.timedelta(hours=12)) == "2.1.10"


def test_nothing_eligible(mod: ModuleType) -> None:
    assert mod.pick_version({"1.0.0": "2026-10-09T00:00:00Z"}, NOW, dt.timedelta(hours=12)) is None
