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

"""Tests for the Kiro CLI permission-policy invariants of sandbox-lint."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sandbox_lint import main
from sandbox_lint.kiro import check_kiro_invariants


def test_empty_config_ok() -> None:
    # Kiro's default is to prompt for shell — a config with no shell policy is
    # safe, unlike OpenCode where a missing permission is flagged.
    assert check_kiro_invariants({}) == []


def test_safe_denybydefault_allowlist_ok() -> None:
    config = {
        "toolsSettings": {
            "shell": {
                "denyByDefault": True,
                "allowedCommands": ["git status", "git fetch", "ls .*"],
            }
        }
    }
    assert check_kiro_invariants(config) == []


def test_shell_in_allowed_tools_flagged() -> None:
    errs = check_kiro_invariants({"allowedTools": ["read", "shell"]})
    assert len(errs) == 1
    assert "allowedTools" in errs[0] and "shell" in errs[0]


def test_execute_bash_alias_in_allowed_tools_flagged() -> None:
    assert check_kiro_invariants({"allowedTools": ["execute_bash"]})


def test_wildcard_allowed_tools_flagged() -> None:
    assert check_kiro_invariants({"allowedTools": ["*"]})
    assert check_kiro_invariants({"allowedTools": ["@builtin"]})


def test_dangerous_allowed_command_flagged() -> None:
    config = {"toolsSettings": {"shell": {"allowedCommands": ["sudo .*", "git status"]}}}
    errs = check_kiro_invariants(config)
    assert any("sudo" in e for e in errs)


def test_curl_allowed_command_flagged() -> None:
    config = {"toolsSettings": {"shell": {"allowedCommands": ["curl .*"]}}}
    errs = check_kiro_invariants(config)
    assert any("curl" in e for e in errs)


def test_deny_before_allow_wins_no_flag() -> None:
    # allowedCommands opens git broadly, but deniedCommands (evaluated first)
    # covers the only dangerous git sample — so no git finding.
    config = {
        "toolsSettings": {
            "shell": {
                "allowedCommands": ["git .*"],
                "deniedCommands": ["git push .*"],
            }
        }
    }
    errs = check_kiro_invariants(config)
    assert not any("git push" in e for e in errs)


def test_aws_in_allowed_tools_flagged() -> None:
    errs = check_kiro_invariants({"allowedTools": ["aws"]})
    assert any("aws" in e for e in errs)


def test_web_fetch_in_allowed_tools_flagged() -> None:
    errs = check_kiro_invariants({"allowedTools": ["web_fetch"]})
    assert any("web_fetch" in e for e in errs)


def test_web_fetch_blanket_trusted_flagged() -> None:
    config = {"toolsSettings": {"web_fetch": {"trusted": [".*"]}}}
    errs = check_kiro_invariants(config)
    assert any("web_fetch.trusted" in e for e in errs)


def test_cli_kiro_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = tmp_path / "agent.json"
    cfg.write_text(json.dumps({"toolsSettings": {"shell": {"denyByDefault": True}}}))
    rc = main(["--kiro", str(cfg)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_cli_kiro_violation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = tmp_path / "agent.json"
    cfg.write_text(json.dumps({"allowedTools": ["shell"]}))
    rc = main(["--kiro", str(cfg)])
    assert rc == 1
    assert "violations" in capsys.readouterr().err
