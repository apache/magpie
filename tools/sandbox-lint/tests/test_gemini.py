# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""Regression tests for missing or weakened Gemini profile controls."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from sandbox_lint import main
from sandbox_lint.gemini import check_gemini_invariants

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def profile() -> tuple[dict[str, Any], dict[str, Any]]:
    settings = json.loads((REPO / ".gemini/settings.json").read_text())
    policy = tomllib.loads((REPO / ".gemini/policies/magpie.toml").read_text())
    return settings, policy


def test_committed_profile(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--gemini", str(REPO / ".gemini")]) == 0
    assert "live enforcement not tested" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("security", "toolSandboxing", False),
        ("security", "disableYoloMode", False),
        ("security", "disableAlwaysAllow", False),
        ("security", "enablePermanentToolApproval", True),
        ("general", "defaultApprovalMode", "auto_edit"),
        ("tools", "sandboxAllowedPaths", ["~"]),
        ("tools", "sandboxNetworkAccess", True),
        ("tools", "sandbox", "docker"),
    ],
)
def test_weakened_settings(profile: tuple[dict, dict], section: str, key: str, value: Any) -> None:
    settings, policy = profile
    settings[section][key] = value
    assert any(key in e for e in check_gemini_invariants(settings, policy))


@pytest.mark.parametrize("paths", [[], [".gemini/policies"], ["./.gemini/policies/magpie.toml"]])
def test_policy_discovery_and_existing_user_policies(profile: tuple[dict, dict], paths: list[str]) -> None:
    settings, policy = profile
    settings["policyPaths"] = paths
    assert any("policyPaths" in e for e in check_gemini_invariants(settings, policy))


@pytest.mark.parametrize("restriction", [{"modes": ["default"]}, {"interactive": True}, {"subagent": "foo"}])
def test_ask_must_cover_every_mode_and_caller(profile: tuple[dict, dict], restriction: dict) -> None:
    settings, policy = profile
    policy["rule"][0].update(restriction)
    assert any("run_shell_command" in e for e in check_gemini_invariants(settings, policy))


def test_shell_ask_cannot_be_promoted_by_native_safe_command_heuristics(profile: tuple[dict, dict]) -> None:
    settings, policy = profile
    del policy["rule"][0]["argsPattern"]
    assert any("argument matcher" in e for e in check_gemini_invariants(settings, policy))


def test_deny_must_outrank_ask(profile: tuple[dict, dict]) -> None:
    settings, policy = profile
    policy["rule"][3]["priority"] = 100
    assert any("gh auth token" in e for e in check_gemini_invariants(settings, policy))


def test_missing_credential_and_config_denies(profile: tuple[dict, dict]) -> None:
    settings, policy = profile
    policy["rule"] = policy["rule"][:4]
    errors = check_gemini_invariants(settings, policy)
    assert any(".ssh/id_rsa" in e for e in errors)
    assert any(".env.local" in e for e in errors)
    assert any("AGENTS.md" in e for e in errors)


def test_new_allow_needs_review(profile: tuple[dict, dict]) -> None:
    settings, policy = profile
    policy["rule"].append({"toolName": "run_shell_command", "decision": "allow", "priority": 999})
    assert any("reviewed scoped reads" in e for e in check_gemini_invariants(settings, policy))


def test_content_search_needs_credential_denies(profile: tuple[dict, dict]) -> None:
    tool = "grep_search"
    settings, policy = profile
    for rule in policy["rule"]:
        names = rule.get("toolName")
        if isinstance(names, list) and tool in names:
            names.remove(tool)
    errors = check_gemini_invariants(settings, policy)
    for protected in (".env", ".env.local", ".gemini/settings.json", ".npmrc", ".pypirc"):
        assert f"magpie.toml: missing native {tool} deny for {protected}" in errors


@pytest.mark.parametrize("change", ["missing", "allow", "default_only", "interactive_only", "query_only"])
def test_web_search_requires_unconditional_approval(profile: tuple[dict, dict], change: str) -> None:
    settings, policy = profile
    rule = next(r for r in policy["rule"] if r.get("toolName") == "google_web_search")
    if change == "missing":
        policy["rule"].remove(rule)
    elif change == "allow":
        rule["decision"] = "allow"
    elif change == "default_only":
        rule["modes"] = ["default"]
    elif change == "interactive_only":
        rule["interactive"] = True
    else:
        rule["argsPattern"] = "documentation"
    assert any("google_web_search ask_user" in e for e in check_gemini_invariants(settings, policy))


@pytest.mark.parametrize(
    "change", ["missing", "broad_prefix", "redirection", "interactive_only", "sandbox_grant"]
)
def test_scoped_reads_cannot_be_widened_or_removed(profile: tuple[dict, dict], change: str) -> None:
    settings, policy = profile
    rule = policy["rule"][-1]
    if change == "missing":
        policy["rule"].pop()
    elif change == "broad_prefix":
        rule["commandPrefix"] = ["gh"]
    elif change == "redirection":
        rule["allowRedirection"] = True
    elif change == "interactive_only":
        rule["interactive"] = True
    else:
        rule["sandbox"] = {"network": True}
    assert any("scoped read" in e for e in check_gemini_invariants(settings, policy))


def test_plan_mode_preserves_scoped_reads(profile: tuple[dict, dict]) -> None:
    settings, policy = profile
    for rule in policy["rule"]:
        if rule.get("modes") == ["plan"]:
            rule["priority"] = 990
    assert any("Plan Mode" in e for e in check_gemini_invariants(settings, policy))


def test_plan_mode_must_remain_read_only(profile: tuple[dict, dict]) -> None:
    settings, policy = profile
    policy["rule"] = [r for r in policy["rule"] if r.get("modes") != ["plan"]]
    assert any("Plan Mode" in e for e in check_gemini_invariants(settings, policy))


def test_reserved_always_allow_priority_is_rejected(profile: tuple[dict, dict]) -> None:
    settings, policy = profile
    policy["rule"][-1]["priority"] = 950
    assert any("remembered approvals" in e for e in check_gemini_invariants(settings, policy))


@pytest.mark.parametrize("value", [None, "disabled", []])
def test_malformed_settings_report_errors(profile: tuple[dict, dict], value: Any) -> None:
    settings, policy = profile
    settings["security"] = value
    assert check_gemini_invariants(settings, policy)


def test_missing_policy_file_fails(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text((REPO / ".gemini/settings.json").read_text())
    with pytest.raises(SystemExit, match="file not found"):
        main(["--gemini", str(tmp_path)])
