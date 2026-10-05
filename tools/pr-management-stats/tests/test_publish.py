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

"""Tests for the always-publish-to-gist helpers (export.md)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import dashboard


def test_session_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = tmp_path / dashboard.SESSION_STATE_FILE
    monkeypatch.setattr(dashboard, "_session_state_path", lambda: state)

    assert dashboard.read_stats_gist_id() is None
    dashboard.store_stats_gist_id("deadbeefdeadbeefdead")
    assert dashboard.read_stats_gist_id() == "deadbeefdeadbeefdead"

    # store must merge, not clobber other keys
    state.write_text(json.dumps({"other": 1, "stats_gist_id": "x"}))
    dashboard.store_stats_gist_id("newid000000000000000")
    data = json.loads(state.read_text())
    assert data["other"] == 1
    assert data["stats_gist_id"] == "newid000000000000000"



def test_session_state_lives_in_the_git_dir_when_not_adopted(tmp_path, monkeypatch):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    root = tmp_path.resolve()
    assert dashboard._session_state_path() == root / ".git" / "apache-magpie" / "session-state.json"
    dashboard.store_stats_gist_id("abc")
    assert (root / ".git" / "apache-magpie" / "session-state.json").is_file()
    assert sorted(p.name for p in root.iterdir()) == [".git"]


def test_session_state_lives_in_tree_when_adopted(tmp_path, monkeypatch):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    monkeypatch.chdir(tmp_path)
    root = tmp_path.resolve()
    assert dashboard._session_state_path() == root / ".apache-magpie-local" / "session-state.json"


def test_a_legacy_repo_root_session_state_is_still_read(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / dashboard.LEGACY_SESSION_STATE_FILE).write_text(json.dumps({"stats_gist_id": "old"}))
    state = tmp_path / "home" / dashboard.SESSION_STATE_FILE
    monkeypatch.setattr(dashboard, "_session_state_path", lambda: state)
    assert dashboard.read_stats_gist_id() == "old"
    dashboard.store_stats_gist_id("new")
    assert json.loads(state.read_text())["stats_gist_id"] == "new"


def test_gist_scope_available_detects_scope(monkeypatch):
    monkeypatch.setattr(
        dashboard.subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout="", stderr="Token scopes: 'gist', 'repo'"),
    )
    assert dashboard.gist_scope_available() is True

    monkeypatch.setattr(
        dashboard.subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout="", stderr="Token scopes: 'repo'"),
    )
    assert dashboard.gist_scope_available() is False


def test_publish_gist_creates_new_and_extracts_id(tmp_path, monkeypatch):
    html = tmp_path / "dashboard.html"
    html.write_text("<html></html>")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(
            returncode=0,
            stdout="https://gist.github.com/potiuk/abc123def456abc123def456\n",
            stderr="",
        )

    monkeypatch.setattr(dashboard.subprocess, "run", fake_run)
    gid = dashboard.publish_gist(html, "apache/airflow", gist_id=None)
    assert gid == "abc123def456abc123def456"
    assert calls[0][:3] == ["gh", "gist", "create"]


def test_publish_gist_patches_existing_in_place(tmp_path, monkeypatch):
    html = tmp_path / "dashboard.html"
    html.write_text("<html>updated</html>")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(dashboard.subprocess, "run", fake_run)
    gid = dashboard.publish_gist(html, "apache/airflow", gist_id="existing000000000000")
    assert gid == "existing000000000000"
    assert "PATCH" in captured["cmd"]
    assert "gists/existing000000000000" in captured["cmd"]
    payload = json.loads(captured["input"])
    assert payload["files"]["dashboard.html"]["content"] == "<html>updated</html>"
