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

"""Tests for the Kiro CLI permission audit."""

from __future__ import annotations

import json
from pathlib import Path

from permission_audit.cli import main
from permission_audit.kiro import audit_kiro, effective_shell_decision


def _kinds(config: dict) -> list[str]:
    return [f.kind for f in audit_kiro(config).forbidden]


def test_empty_config_is_clean():
    # Kiro's default prompts for shell — no config is safe.
    assert not audit_kiro({}).has_findings


def test_safe_denybydefault_allowlist_is_clean():
    config = {"toolsSettings": {"shell": {"denyByDefault": True, "allowedCommands": ["git status", "ls .*"]}}}
    assert not audit_kiro(config).has_findings


def test_shell_in_allowed_tools_is_forbidden():
    r = audit_kiro({"allowedTools": ["read", "shell"]})
    assert [f.kind for f in r.forbidden] == ["shell-allow-all"]
    assert r.forbidden[0].json_pointer == ".allowedTools"


def test_execute_bash_alias_forbidden():
    assert _kinds({"allowedTools": ["execute_bash"]}) == ["shell-allow-all"]


def test_wildcard_and_builtin_forbidden():
    assert _kinds({"allowedTools": ["*"]}) == ["shell-allow-all"]
    assert _kinds({"allowedTools": ["@builtin"]}) == ["shell-allow-all"]


def test_blanket_shell_reported_once_not_per_command():
    r = audit_kiro({"allowedTools": ["shell"]})
    assert len(r.forbidden) == 1


def test_dangerous_allowed_command_flagged():
    config = {"toolsSettings": {"shell": {"allowedCommands": ["sudo .*", "git status"]}}}
    r = audit_kiro(config)
    kinds = [f.kind for f in r.forbidden]
    assert "dangerous-allow" in kinds
    assert any("sudo" in f.detail for f in r.forbidden)


def test_deny_before_allow_wins_no_flag():
    config = {"toolsSettings": {"shell": {"allowedCommands": ["git .*"], "deniedCommands": ["git push .*"]}}}
    r = audit_kiro(config)
    assert not any("git push" in f.detail for f in r.forbidden)


def test_aws_tool_forbidden():
    assert _kinds({"allowedTools": ["aws"]}) == ["exfil-allow"]


def test_web_fetch_tool_forbidden():
    assert _kinds({"allowedTools": ["web_fetch"]}) == ["exfil-allow"]


def test_web_fetch_blanket_trusted_forbidden():
    r = audit_kiro({"toolsSettings": {"web_fetch": {"trusted": [".*"]}}})
    assert [f.kind for f in r.forbidden] == ["exfil-allow"]


def test_effective_shell_decision_deny_before_allow():
    cfg = {"allowedCommands": ["git .*"], "deniedCommands": ["git push .*"]}
    assert effective_shell_decision(cfg, "git status") == ("allow", "git .*")
    assert effective_shell_decision(cfg, "git push origin main") == ("deny", "git push .*")
    assert effective_shell_decision({}, "ls -la") == ("ask", None)
    assert effective_shell_decision({"denyByDefault": True}, "ls -la") == ("deny", None)


def test_cli_audit_kiro_denies_and_exits_1(tmp_path: Path, capsys):
    cfg = tmp_path / "agent.json"
    cfg.write_text(json.dumps({"allowedTools": ["shell"]}))
    rc = main(["audit-kiro", str(cfg)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["harness"] == "kiro"
    assert out["forbidden"][0]["kind"] == "shell-allow-all"


def test_cli_audit_kiro_clean_exits_0(tmp_path: Path, capsys):
    cfg = tmp_path / "agent.json"
    cfg.write_text(json.dumps({"toolsSettings": {"shell": {"denyByDefault": True}}}))
    rc = main(["audit-kiro", str(cfg)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["forbidden"] == []
