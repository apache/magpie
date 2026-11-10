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

"""Tests for ``container-gateway settings``: the proposal and its guarded merge."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

import pytest

from container_gateway import __main__ as cli
from container_gateway import settings


def _prop(run_dir: Path) -> settings.Proposal:
    return settings.proposal(run_dir, {"podman": run_dir / "podman.sock", "docker": run_dir / "docker.sock"})


def test_proposal_uses_absolute_unix_urls_and_both_sockets(tmp_path: Path) -> None:
    run = tmp_path / "proj" / ".apache-magpie-local" / "run"
    p = _prop(run).as_dict()
    assert p["env"] == {
        "CONTAINER_HOST": f"unix://{run}/podman.sock",
        "DOCKER_HOST": f"unix://{run}/docker.sock",
    }
    assert p["env"]["CONTAINER_HOST"].startswith("unix:///")  # never unix://./relative
    assert p["sandbox"] == {"network": {"allowUnixSockets": [f"{run}/podman.sock", f"{run}/docker.sock"]}}


def test_proposal_refuses_a_relative_run_dir() -> None:
    with pytest.raises(settings.SettingsError):
        _prop(Path("relative/run"))


def test_apply_creates_an_absent_file(tmp_path: Path) -> None:
    target = tmp_path / ".claude" / "settings.local.json"
    result = settings.apply(target, _prop(tmp_path / "run"))
    assert result.status == "written"
    data = json.loads(target.read_text())
    assert set(data["env"]) == {"CONTAINER_HOST", "DOCKER_HOST"}
    assert len(data["sandbox"]["network"]["allowUnixSockets"]) == 2
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_apply_is_additive_and_keeps_everything_else(tmp_path: Path) -> None:
    target = tmp_path / "settings.local.json"
    existing = {
        "permissions": {"allow": ["Bash(ls *)"]},
        "env": {"OTHER": "1"},
        "sandbox": {
            "enabled": True,
            "network": {
                "allowUnixSockets": ["/run/user/1000/gnupg/S.gpg-agent.ssh"],
                "allowedDomains": ["x"],
            },
            "filesystem": {"allowWrite": ["~/.cache"]},
        },
    }
    target.write_text(json.dumps(existing))
    os.chmod(target, 0o700)  # not the 0o600 a fresh write gets
    result = settings.apply(target, _prop(tmp_path / "run"))
    data = json.loads(target.read_text())
    assert result.status == "written" and result.conflicts == {}
    assert data["permissions"] == existing["permissions"]
    assert data["env"]["OTHER"] == "1"
    assert data["sandbox"]["enabled"] is True
    assert data["sandbox"]["filesystem"] == existing["sandbox"]["filesystem"]
    assert data["sandbox"]["network"]["allowedDomains"] == ["x"]
    socks = data["sandbox"]["network"]["allowUnixSockets"]
    assert socks[0] == "/run/user/1000/gnupg/S.gpg-agent.ssh" and len(socks) == 3
    assert stat.S_IMODE(target.stat().st_mode) == 0o700  # mode kept


def test_apply_is_idempotent_and_never_rewrites_an_unchanged_file(tmp_path: Path) -> None:
    target = tmp_path / "settings.local.json"
    prop = _prop(tmp_path / "run")
    settings.apply(target, prop)
    before = target.stat().st_mtime_ns
    result = settings.apply(target, prop)
    assert result.status == "unchanged" and result.added_env == {} and result.added_sockets == []
    assert target.stat().st_mtime_ns == before
    assert len(json.loads(target.read_text())["sandbox"]["network"]["allowUnixSockets"]) == 2


def test_a_different_existing_env_value_is_a_conflict_never_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "settings.local.json"
    target.write_text(json.dumps({"env": {"DOCKER_HOST": "tcp://127.0.0.1:2375"}}))
    result = settings.apply(target, _prop(tmp_path / "run"))
    data = json.loads(target.read_text())
    assert data["env"]["DOCKER_HOST"] == "tcp://127.0.0.1:2375"
    assert result.conflicts == {
        "DOCKER_HOST": {"current": "tcp://127.0.0.1:2375", "proposed": f"unix://{tmp_path}/run/docker.sock"}
    }
    # The rest of the block is still added.
    assert "CONTAINER_HOST" in data["env"] and result.status == "written"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "not valid JSON"),
        ("[1, 2]", "not a JSON object"),
        ('{"env": []}', "`env` is not a JSON object"),
        ('{"sandbox": {"network": {"allowUnixSockets": "x"}}}', "allowUnixSockets"),
    ],
)
def test_an_unmergeable_file_is_refused_and_left_alone(tmp_path: Path, content: str, message: str) -> None:
    target = tmp_path / "settings.local.json"
    target.write_text(content)
    with pytest.raises(settings.SettingsError, match=message):
        settings.apply(target, _prop(tmp_path / "run"))
    assert target.read_text() == content


def test_a_symlinked_target_is_refused(tmp_path: Path) -> None:
    real = tmp_path / "elsewhere.json"
    real.write_text("{}")
    target = tmp_path / "settings.local.json"
    target.symlink_to(real)
    with pytest.raises(settings.SettingsError, match="symlink"):
        settings.apply(target, _prop(tmp_path / "run"))
    assert real.read_text() == "{}"


def test_a_concurrent_change_aborts_the_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "settings.local.json"
    target.write_text('{"env": {}}')
    real_merge = settings._merge

    def merge_then_edit(data: dict, prop: settings.Proposal):  # an editor saving mid-merge
        out = real_merge(data, prop)
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("\n")
        return out

    monkeypatch.setattr(settings, "_merge", merge_then_edit)
    with pytest.raises(settings.SettingsError, match="changed while it was being merged"):
        settings.apply(target, _prop(tmp_path / "run"))
    assert json.loads(target.read_text()) == {"env": {}}
    assert not list(tmp_path.glob(".settings.local.json.*"))  # no temp file left behind


def test_a_rename_replace_during_the_merge_aborts_the_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An editor (or the harness) that saves by writing a temp file and renaming
    # it over the target puts a new inode at the path; the descriptor apply()
    # holds never sees it change, so the check has to look at the name.
    target = tmp_path / "settings.local.json"
    target.write_text('{"env": {}}')
    real_merge = settings._merge

    def merge_then_rename(data: dict, prop: settings.Proposal):
        out = real_merge(data, prop)
        new = tmp_path / "editor-save.tmp"
        new.write_text('{"env": {"MINE": "1"}}')
        os.replace(new, target)
        return out

    monkeypatch.setattr(settings, "_merge", merge_then_rename)
    with pytest.raises(settings.SettingsError, match="changed while it was being merged"):
        settings.apply(target, _prop(tmp_path / "run"))
    assert json.loads(target.read_text()) == {"env": {"MINE": "1"}}  # the other writer's save survives
    assert not list(tmp_path.glob(".settings.local.json.*"))


def test_a_symlinked_parent_directory_is_refused(tmp_path: Path) -> None:
    # A repository-controlled `.claude` symlink must not redirect the write.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / ".claude").symlink_to(elsewhere)
    with pytest.raises(settings.SettingsError, match="symlink"):
        settings.apply(tmp_path / ".claude" / "settings.local.json", _prop(tmp_path / "run"))
    assert list(elsewhere.iterdir()) == []


def test_only_the_last_directory_is_created(tmp_path: Path) -> None:
    with pytest.raises(settings.SettingsError, match="does not exist"):
        settings.apply(tmp_path / "missing" / ".claude" / "settings.local.json", _prop(tmp_path / "run"))
    assert not (tmp_path / "missing").exists()


def _adopted_project() -> Path:
    # Short, so the socket paths stay under the unix socket path limit.
    project = Path(tempfile.mkdtemp(prefix="cg-"))
    (project / ".apache-magpie.lock").write_text("method: local\n", encoding="utf-8")
    return project


def test_cli_prints_a_proposal_and_applies_with_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    project = _adopted_project()
    run = project.resolve() / ".apache-magpie-local" / "run"  # the gateway anchors on the resolved root
    target = project / ".claude" / "settings.local.json"
    try:
        assert cli.main(["settings", "--project", str(project)]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["proposal"]["env"]["CONTAINER_HOST"] == f"unix://{run}/podman.sock"
        assert not target.exists()  # printing never writes

        args = ["settings", "--project", str(project), "--apply", str(target)]
        assert cli.main(args) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "written"
        assert cli.main(args) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "unchanged"

        target.write_text(json.dumps({"env": {"CONTAINER_HOST": "unix:///elsewhere.sock"}}))
        assert cli.main(args) == 3  # conflict reported, not overwritten
        written = json.loads(capsys.readouterr().out)
        assert written["status"] == "written" and written["added_sockets"]  # the rest was still added

        target.write_text("{broken")
        assert cli.main(args) == 2
        assert "not valid JSON" in capsys.readouterr().err
    finally:
        shutil.rmtree(project)


def test_cli_settings_takes_no_run_dir(capsys: pytest.CaptureFixture[str]) -> None:
    # The block goes into allowUnixSockets, so a caller-chosen directory could
    # name a real daemon socket (`--run-dir /var/run`): the option does not exist.
    project = _adopted_project()
    try:
        with pytest.raises(SystemExit) as exc:
            cli.main(["settings", "--project", str(project), "--run-dir", "/var/run"])
        assert exc.value.code == 2
    finally:
        shutil.rmtree(project)
    capsys.readouterr()


def test_cli_settings_refuses_a_project_serve_would_refuse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Neither adopted nor a git repository: serve has no run directory, so
    # there is no block to propose.
    with pytest.raises(SystemExit) as exc:
        cli.main(["settings", "--project", str(tmp_path)])
    assert exc.value.code == 2
    assert "pass --run-dir" in capsys.readouterr().err


def test_cli_settings_refuses_a_symlinked_run_dir_component(capsys: pytest.CaptureFixture[str]) -> None:
    # A planted `.apache-magpie-local -> ~/.docker` style link: serve refuses
    # it, so settings must not authorize sockets under it either.
    project = _adopted_project()
    elsewhere = Path(tempfile.mkdtemp(prefix="cg-x-"))
    try:
        (project / ".apache-magpie-local").symlink_to(elsewhere)
        target = project / ".claude" / "settings.local.json"
        with pytest.raises(SystemExit) as exc:
            cli.main(["settings", "--project", str(project), "--apply", str(target)])
        assert exc.value.code == 2
        assert not target.exists()
    finally:
        shutil.rmtree(project)
        shutil.rmtree(elsewhere)
    capsys.readouterr()
