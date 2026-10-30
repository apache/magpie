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

"""Tests for the user-scope Antigravity profile checks of sandbox-lint."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sandbox_lint import main
from sandbox_lint.antigravity import (
    GH_API_MUTATION,
    check_antigravity_hooks,
    check_antigravity_settings,
    required_rules,
)

TOOL_ROOT = Path(__file__).resolve().parents[1]
PROFILE = TOOL_ROOT.parent / "agent-isolation" / "antigravity"
BASELINE = json.loads((TOOL_ROOT / "expected.json").read_text())
SETTINGS = json.loads((PROFILE / "settings.json").read_text())
HOOKS = json.loads((PROFILE / "hooks.json").read_text())


def test_shipped_profile_passes() -> None:
    assert check_antigravity_settings(SETTINGS, BASELINE) == []
    assert check_antigravity_hooks(HOOKS) == []


def test_cli_lints_shipped_profile_directory(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--antigravity", str(PROFILE)]) == 0
    assert "sandbox-lint: OK" in capsys.readouterr().out


def test_cli_reads_hooks_from_a_separate_file(tmp_path: Path) -> None:
    # The user's live profile keeps hooks in ~/.gemini/config, not beside settings.json.
    # The install merge writes absolute home paths, which is what a live profile must hold.
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(SETTINGS).replace("(~/", f"({Path.home()}/"))
    hooks = tmp_path / "config" / "hooks.json"
    hooks.parent.mkdir()
    hooks.write_text(json.dumps(HOOKS))
    assert main(["--antigravity", str(settings), "--antigravity-hooks", str(hooks)]) == 0


def test_a_live_profile_with_tilde_rules_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Whether Antigravity expands ~ in path rules is unverified, so a live ~/ deny may enforce nothing.
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(SETTINGS))
    (tmp_path / "hooks.json").write_text(json.dumps(HOOKS))
    assert main(["--antigravity", str(settings)]) == 1
    assert "read_file(~/.ssh) uses ~/" in capsys.readouterr().err


def test_live_check_reports_each_tilde_rule() -> None:
    errors = check_antigravity_settings(SETTINGS, BASELINE, home="/home/maintainer", live=True)
    assert any("(/home/maintainer/.ssh)" in e for e in errors)


def test_required_rules_follow_the_claude_baseline() -> None:
    deny, ask = required_rules(BASELINE)
    assert "read_file(~/.ssh)" in deny
    assert "command(gh auth token)" in deny
    assert "write_file(.agents/hooks.json)" in deny
    assert "command(git push)" in ask
    assert "command(gh pr create)" in ask
    assert ask.count(GH_API_MUTATION) == 1
    assert not any("~/.claude" in rule for rule in deny + ask)


def test_absolute_home_paths_match_the_shipped_form() -> None:
    settings = copy.deepcopy(SETTINGS)
    settings["permissions"]["deny"] = [
        rule.replace("(~/", "(/home/maintainer/") for rule in settings["permissions"]["deny"]
    ]
    assert check_antigravity_settings(settings, BASELINE, home="/home/maintainer") == []


@pytest.mark.parametrize(
    "key, value, message",
    [
        ("enableTerminalSandbox", False, "enableTerminalSandbox must be true"),
        ("toolPermission", "always-proceed", "toolPermission must be one of"),
        ("allowNonWorkspaceAccess", True, "allowNonWorkspaceAccess must be false"),
        ("agentMode", "auto", "agentMode must be unset"),
        ("agentMode", "accept-edits", "agentMode must be unset"),
    ],
)
def test_weakened_setting_is_reported(key: str, value: object, message: str) -> None:
    settings = {**SETTINGS, key: value}
    assert any(message in e for e in check_antigravity_settings(settings, BASELINE))


@pytest.mark.parametrize("key", ["deny", "ask"])
def test_missing_required_rule_is_reported(key: str) -> None:
    settings = copy.deepcopy(SETTINGS)
    removed = settings["permissions"][key].pop(0)
    errors = check_antigravity_settings(settings, BASELINE)
    assert f"settings.json: permissions.{key} is missing {removed}" in errors


@pytest.mark.parametrize("rule", ["command(*)", "write_file(*)", "unsandboxed(git push)"])
def test_broad_allow_is_reported(rule: str) -> None:
    settings = copy.deepcopy(SETTINGS)
    settings["permissions"]["allow"].append(rule)
    assert any(rule in e for e in check_antigravity_settings(settings, BASELINE))


def _guard(command: str, matcher: str = "run_command", **extra: object) -> dict:
    return {
        "magpie-agent-guard": {
            **extra,
            "PreToolUse": [{"matcher": matcher, "hooks": [{"type": "command", "command": command}]}],
        }
    }


GUARD = 'python3 "/opt/magpie/tools/agent-guard/src/agent_guard/__init__.py" --antigravity'


@pytest.mark.parametrize(
    "hooks, ok",
    [
        (_guard(GUARD), True),
        (_guard(GUARD, matcher="*"), True),
        (_guard(GUARD, matcher="run_command|view_file"), True),
        (_guard(GUARD, matcher="view_file"), False),
        (_guard(GUARD, enabled=False), False),
        (_guard(GUARD.replace("--antigravity", "--gemini")), False),
        ({**_guard(GUARD), "second": _guard(GUARD)["magpie-agent-guard"]}, False),
        ({}, False),
    ],
)
def test_guard_registration(hooks: dict, ok: bool) -> None:
    assert (check_antigravity_hooks(hooks) == []) is ok
