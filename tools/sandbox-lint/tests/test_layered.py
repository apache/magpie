# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""The committed floor, the local template, and the family MCP registry."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from sandbox_lint import (
    REQUIRED_VETTED_OP_READ_ALLOW,
    check_invariants,
    main,
    merge_layers,
    registry_errors,
    split_errors,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FLOOR = REPO_ROOT / ".claude" / "settings.json"
LOCAL_TEMPLATE = REPO_ROOT / "tools" / "agent-isolation" / "claude-settings.local.template.json"
REGISTRY = REPO_ROOT / "plugins" / "magpie-setup" / "skills" / "setup" / "family-mcp-allows.json"


def _load(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text())


def test_merge_concatenates_lists_and_recurses() -> None:
    floor = {"sandbox": {"enabled": True, "filesystem": {"allowRead": ["."]}}, "permissions": {"deny": ["a"]}}
    local = {"sandbox": {"filesystem": {"allowRead": [".", "~/x"]}}, "permissions": {"allow": ["b"]}}
    assert merge_layers(floor, local) == {
        "sandbox": {"enabled": True, "filesystem": {"allowRead": [".", "~/x"]}},
        "permissions": {"deny": ["a"], "allow": ["b"]},
    }


@pytest.mark.parametrize(
    "floor,local,needle",
    [
        ({"permissions": {"allow": ["Bash(ls *)"]}}, {}, "floor permissions.allow"),
        ({}, {"permissions": {"deny": ["Bash(rm *)"]}}, "permissions.deny"),
        ({}, {"permissions": {"ask": ["Bash(git push *)"]}}, "permissions.ask"),
        ({}, {"permissions": {"allow": ["mcp__ponymail__get_email"]}}, "is an MCP tool"),
        ({"sandbox": {"enabled": True}}, {"sandbox": {"enabled": False}}, "$.sandbox.enabled"),
    ],
)
def test_split_rules(floor: dict[str, Any], local: dict[str, Any], needle: str) -> None:
    errors = split_errors(floor, local)
    assert any(needle in e for e in errors), errors


def test_floor_may_hold_derived_mcp_and_the_vetted_op_read_pair() -> None:
    floor = {"permissions": {"allow": ["mcp__ponymail__get_email", *REQUIRED_VETTED_OP_READ_ALLOW]}}
    assert split_errors(floor, {}) == []


def test_the_shipped_split_is_clean() -> None:
    assert split_errors(_load(FLOOR), _load(LOCAL_TEMPLATE)) == []


def test_the_floor_alone_is_safe() -> None:
    # A contributor with no local file still gets every protective rule.
    assert check_invariants(_load(FLOOR)) == []


def test_floor_mcp_allows_are_the_registry_for_every_family() -> None:
    # The framework checkout links every family, so its committed MCP allows
    # are exactly what the registry derives for all of them.
    assert registry_errors(_load(FLOOR), _load(REGISTRY)) == []


def test_registry_drift_is_reported_both_ways() -> None:
    registry = {"servers": {"ponymail": {"families": ["security"], "tools": ["get_email", "get_thread"]}}}
    floor = {"permissions": {"allow": ["mcp__ponymail__get_email", "mcp__other__x"]}}
    errors = registry_errors(floor, registry)
    assert any("missing 'mcp__ponymail__get_thread'" in e for e in errors)
    assert any("'mcp__other__x' is not in" in e for e in errors)


def test_merge_handles_lists_of_objects() -> None:
    entry = {"name": "GH_TOKEN", "mode": "deny"}
    merged = merge_layers(
        {"c": {"envVars": [entry]}}, {"c": {"envVars": [entry, {"name": "X", "mode": "deny"}]}}
    )
    assert merged["c"]["envVars"] == [entry, {"name": "X", "mode": "deny"}]


def test_cli_lints_the_layered_view_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings, _ = _project_with(tmp_path, _load(LOCAL_TEMPLATE))
    expected = settings.parent.parent / "tools" / "sandbox-lint" / "expected.json"
    expected.parent.mkdir(parents=True)
    expected.write_text((REPO_ROOT / "tools" / "sandbox-lint" / "expected.json").read_text())
    monkeypatch.chdir(settings.parent.parent)
    assert main([]) == 0
    assert "claude-settings.local.template.json" in capsys.readouterr().out


def test_cli_without_a_template_lints_the_file_alone(tmp_path: Path) -> None:
    # A project that has no local template (any adopter) lints its own file.
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(merge_layers(_load(FLOOR), _load(LOCAL_TEMPLATE))))
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert main(["--settings", str(settings), "--expected", str(expected)]) == 0
    finally:
        os.chdir(cwd)


def _project_with(tmp_path: Path, template: dict[str, Any], *, registry: bool = True) -> tuple[Path, Path]:
    root = tmp_path / "project"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "settings.json").write_text(FLOOR.read_text())
    tpl = root / "tools" / "agent-isolation" / "claude-settings.local.template.json"
    tpl.parent.mkdir(parents=True)
    tpl.write_text(json.dumps(template))
    if registry:
        reg = root / "plugins" / "magpie-setup" / "skills" / "setup" / "family-mcp-allows.json"
        reg.parent.mkdir(parents=True)
        reg.write_text(REGISTRY.read_text())
    return root / ".claude" / "settings.json", tpl


@pytest.mark.parametrize(
    "extra,needle",
    [
        ({"permissions": {"deny": ["Bash(rm *)"]}}, "permissions.deny"),
        ({"sandbox": {"enabled": False}}, "$.sandbox.enabled"),
    ],
)
def test_cli_fails_on_a_split_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], extra: dict[str, Any], needle: str
) -> None:
    template = merge_layers(_load(LOCAL_TEMPLATE), extra)
    settings, _ = _project_with(tmp_path, template)
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    assert main(["--settings", str(settings), "--expected", str(expected)]) == 1
    assert needle in capsys.readouterr().err


def test_cli_uses_an_explicit_local_template(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"permissions": {"ask": ["Bash(git push *)"]}}))
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    settings, _ = _project_with(tmp_path, _load(LOCAL_TEMPLATE))
    assert main(["--settings", str(settings), "--expected", str(expected), "--local-template", str(bad)]) == 1
    assert "permissions.ask" in capsys.readouterr().err


@pytest.mark.parametrize(
    "local,rc",
    [
        ({"permissions": {"allow": ["Bash(make *)", "mcp__other__read"]}}, 0),
        ({"permissions": {"deny": ["Bash(rm *)"]}}, 0),
        ({"sandbox": {"enabled": False}}, 1),
        ({"sandbox": {"filesystem": {"allowRead": ["~/.ssh"]}}}, 1),
    ],
)
def test_default_run_checks_the_live_local_layer(tmp_path: Path, local: dict[str, Any], rc: int) -> None:
    # The local file in force here may add things, but may not weaken a control.
    settings, _ = _project_with(tmp_path, _load(LOCAL_TEMPLATE))
    (settings.parent / "settings.local.json").write_text(json.dumps(local))
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    assert main(["--settings", str(settings), "--expected", str(expected)]) == rc


def test_an_equal_local_value_is_not_an_override() -> None:
    # /sandbox may write the same value into settings.local.json.
    assert split_errors({"sandbox": {"enabled": True}}, {"sandbox": {"enabled": True}}) == []


def test_a_missing_registry_beside_the_template_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings, _ = _project_with(tmp_path, _load(LOCAL_TEMPLATE), registry=False)
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    assert main(["--settings", str(settings), "--expected", str(expected)]) == 1
    assert "family-mcp-allows.json is missing" in capsys.readouterr().err
