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

"""Tests for the OpenCode permission audit."""

from __future__ import annotations

import json
from pathlib import Path

from permission_audit.cli import main
from permission_audit.opencode import (
    audit_opencode,
    bash_default,
    effective_bash_decision,
)


def _kinds(config: dict) -> list[str]:
    return [f.kind for f in audit_opencode(config).forbidden]


def test_empty_config_is_clean():
    assert not audit_opencode({}).has_findings


def test_ask_string_is_clean():
    assert not audit_opencode({"permission": "ask"}).has_findings


def test_deny_string_is_clean():
    assert not audit_opencode({"permission": "deny"}).has_findings


def test_blanket_allow_string_is_forbidden():
    r = audit_opencode({"permission": "allow"})
    assert [f.kind for f in r.forbidden] == ["blanket-allow"]
    assert r.forbidden[0].json_pointer == ".permission"


def test_bash_string_allow_is_forbidden():
    assert _kinds({"permission": {"bash": "allow"}}) == ["bash-allow-all"]


def test_bash_star_allow_is_forbidden():
    assert _kinds({"permission": {"bash": {"*": "allow"}}}) == ["bash-allow-all"]


def test_bash_star_ask_is_clean():
    assert not audit_opencode({"permission": {"bash": {"*": "ask"}}}).has_findings


def test_specific_dangerous_allow_while_default_asks():
    # Default asks, but a specific rule opens `git *` → git push is auto-approved.
    config = {"permission": {"bash": {"*": "ask", "git *": "allow"}}}
    r = audit_opencode(config)
    kinds = [f.kind for f in r.forbidden]
    assert "dangerous-allow" in kinds
    assert "bash-allow-all" not in kinds
    assert any("git *" in f.json_pointer for f in r.forbidden)


def test_default_allow_does_not_double_report_each_command():
    # When the default is allow, report it once, not once per dangerous sample.
    r = audit_opencode({"permission": {"bash": {"*": "allow"}}})
    assert len(r.forbidden) == 1
    assert r.forbidden[0].kind == "bash-allow-all"


def test_last_match_wins_deny_overrides_earlier_allow():
    # git * allow, then git push * deny → git push is denied, so no finding.
    config = {"permission": {"bash": {"*": "ask", "git *": "allow", "git push *": "deny"}}}
    r = audit_opencode(config)
    # `git *` still allows other dangerous-ish git, but our sample "git push origin main"
    # is denied by the later rule; no dangerous-allow for git push.
    assert not any(f.json_pointer == '.permission.bash["git push *"]' for f in r.forbidden)


def test_safe_narrow_allow_is_clean():
    config = {"permission": {"bash": {"*": "ask", "lychee *": "allow", "ls *": "allow"}}}
    assert not audit_opencode(config).has_findings


def test_bash_default_helper():
    assert bash_default("allow") == "allow"
    assert bash_default({"*": "deny"}) == "deny"
    assert bash_default({"git *": "allow"}) is None  # no explicit default
    assert bash_default(None) is None


def test_effective_decision_last_match_wins():
    rules = {"*": "ask", "git *": "allow", "git push *": "deny"}
    assert effective_bash_decision(rules, "git status") == ("allow", "git *")
    assert effective_bash_decision(rules, "git push origin") == ("deny", "git push *")
    assert effective_bash_decision(rules, "ls -la") == ("ask", "*")


def test_cli_audit_opencode_denies_and_exits_1(tmp_path: Path, capsys):
    cfg = tmp_path / "opencode.json"
    cfg.write_text(json.dumps({"permission": {"bash": "allow"}}))
    rc = main(["audit-opencode", str(cfg)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["harness"] == "opencode"
    assert out["forbidden"][0]["kind"] == "bash-allow-all"


def test_cli_audit_opencode_clean_exits_0(tmp_path: Path, capsys):
    cfg = tmp_path / "opencode.json"
    cfg.write_text(json.dumps({"permission": {"bash": {"*": "ask"}}}))
    rc = main(["audit-opencode", str(cfg)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["forbidden"] == []
