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
import json
from pathlib import Path

import pytest

from permission_audit.cli import main


def _write_settings(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_audit_clean_file_exits_zero(tmp_path, capsys):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": ["Bash(lychee *)"]}})
    rc = main(["audit", str(p), "--families", ""])
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert rc == 0
    assert out["forbidden"] == []
    # missing_recommended scoped to "" family — only lychee, which is present
    assert out["missing_recommended"] == []


def test_audit_release_management_family_flags_missing_auth(tmp_path, capsys):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": ["Bash(lychee *)"]}})
    rc = main(["audit", str(p), "--families", "release-management"])
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert rc == 0
    assert out["forbidden"] == []
    missing_patterns = {m["pattern"] for m in out["missing_recommended"]}
    assert "mcp__gmail-plaintext__check_auth" in missing_patterns


def test_audit_release_management_family_passes_when_present(tmp_path, capsys):
    p = tmp_path / "settings.local.json"
    _write_settings(
        p,
        {
            "permissions": {
                "allow": [
                    "Bash(lychee *)",
                    "mcp__gmail-plaintext__check_auth",
                ]
            }
        },
    )
    rc = main(["audit", str(p), "--families", "release-management"])
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert rc == 0
    assert out["forbidden"] == []
    assert out["missing_recommended"] == []


def test_audit_release_management_asf_organization_flags_ponymail(tmp_path, capsys):
    p = tmp_path / "settings.local.json"
    _write_settings(
        p,
        {
            "permissions": {
                "allow": [
                    "Bash(lychee *)",
                    "mcp__gmail-plaintext__check_auth",
                ]
            }
        },
    )
    rc = main(["audit", str(p), "--families", "release-management", "--organization", "ASF"])
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert rc == 0
    missing_patterns = {m["pattern"] for m in out["missing_recommended"]}
    assert "mcp__ponymail__auth_status" in missing_patterns
    assert "mcp__ponymail__get_thread" in missing_patterns


def test_audit_forbidden_exits_nonzero(tmp_path, capsys):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": ["Bash(uv run *)"]}})
    rc = main(["audit", str(p)])
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert rc == 1
    assert len(out["forbidden"]) == 1
    assert out["forbidden"][0]["pattern"] == "Bash(uv run *)"
    assert out["forbidden"][0]["json_pointer"] == ".permissions.allow[0]"


def test_apply_add_and_remove(tmp_path, capsys):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": ["Bash(uv run *)"]}})
    rc = main(
        [
            "apply",
            str(p),
            "--add",
            "Bash(lychee *)",
            "--remove",
            "Bash(uv run *)",
        ]
    )
    assert rc == 0
    final = json.loads(p.read_text())["permissions"]["allow"]
    assert final == ["Bash(lychee *)"]


def test_apply_with_no_changes_returns_2(tmp_path):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": []}})
    rc = main(["apply", str(p)])
    assert rc == 2


def test_list_known_dumps_canonical_lists(capsys):
    rc = main(["list-known"])
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert rc == 0
    assert "Bash(uv run *)" in out["forbidden_patterns"]
    assert "Bash(python3 *)" in out["forbidden_patterns"]
    assert "Bash(lychee *)" in out["recommended_by_family"][""]
    security_recs = out["recommended_by_family"]["security"]
    assert "mcp__claude_ai_Gmail__get_thread" in security_recs
    assert "mcp__claude_ai_Gmail__get_message" in security_recs
    assert "mcp__claude_ai_Gmail__list_drafts" in security_recs
    assert "mcp__claude_ai_Gmail__get_draft" in security_recs
    assert "mcp__gmail-plaintext__check_auth" in security_recs
    assert "mcp__claude_ai_Gmail__list_labels" not in security_recs
    assert out["recommended_by_family"]["release-management"] == ["mcp__gmail-plaintext__check_auth"]


def test_no_args_exits_with_error_code(capsys):
    with pytest.raises(SystemExit) as e:
        main([])
    # argparse uses exit code 2 for missing required subcommand
    assert e.value.code == 2
