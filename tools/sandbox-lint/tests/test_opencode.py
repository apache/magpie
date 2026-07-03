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

"""Tests for the OpenCode permission-policy invariants of sandbox-lint."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sandbox_lint import main
from sandbox_lint.opencode import check_opencode_invariants


def test_missing_permission_flags() -> None:
    errs = check_opencode_invariants({})
    assert errs and "missing" in errs[0]


def test_blanket_allow_flagged() -> None:
    errs = check_opencode_invariants({"permission": "allow"})
    assert len(errs) == 1
    assert "blanket" in errs[0] or "allow" in errs[0]


def test_ask_string_ok() -> None:
    assert check_opencode_invariants({"permission": "ask"}) == []


def test_bash_default_allow_flagged() -> None:
    errs = check_opencode_invariants({"permission": {"bash": {"*": "allow"}}})
    assert any("default decision" in e for e in errs)


def test_bash_string_allow_flagged() -> None:
    errs = check_opencode_invariants({"permission": {"bash": "allow"}})
    assert any("allow" in e for e in errs)


def test_safe_policy_ok() -> None:
    config = {"permission": {"bash": {"*": "ask", "ls *": "allow", "lychee *": "allow"}}}
    assert check_opencode_invariants(config) == []


def test_specific_dangerous_allow_flagged() -> None:
    config = {"permission": {"bash": {"*": "ask", "sudo *": "allow"}}}
    errs = check_opencode_invariants(config)
    assert any("sudo" in e for e in errs)


def test_last_match_deny_wins_no_flag() -> None:
    config = {"permission": {"bash": {"*": "ask", "git *": "allow", "git push *": "deny"}}}
    errs = check_opencode_invariants(config)
    assert not any("git push" in e for e in errs)


def test_webfetch_allow_flagged() -> None:
    config = {"permission": {"bash": {"*": "ask"}, "webfetch": "allow"}}
    errs = check_opencode_invariants(config)
    assert any("webfetch" in e for e in errs)


def test_external_directory_allow_flagged() -> None:
    config = {"permission": {"bash": {"*": "ask"}, "external_directory": "allow"}}
    errs = check_opencode_invariants(config)
    assert any("external_directory" in e for e in errs)


def test_cli_opencode_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = tmp_path / "opencode.json"
    cfg.write_text(json.dumps({"permission": {"bash": {"*": "ask"}}}))
    rc = main(["--opencode", str(cfg)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_cli_opencode_violation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = tmp_path / "opencode.json"
    cfg.write_text(json.dumps({"permission": "allow"}))
    rc = main(["--opencode", str(cfg)])
    assert rc == 1
    assert "violations" in capsys.readouterr().err
