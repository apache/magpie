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
import stat
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
    os.chmod(target, 0o640)
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
    assert stat.S_IMODE(target.stat().st_mode) == 0o640  # mode kept


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


def test_cli_prints_a_proposal_and_applies_with_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = tmp_path / "run"
    target = tmp_path / "settings.local.json"
    assert cli.main(["settings", "--project", str(tmp_path), "--run-dir", str(run)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proposal"]["env"]["CONTAINER_HOST"] == f"unix://{run}/podman.sock"
    assert not target.exists()  # printing never writes

    args = ["settings", "--project", str(tmp_path), "--run-dir", str(run), "--apply", str(target)]
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "written"
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "unchanged"

    target.write_text(json.dumps({"env": {"CONTAINER_HOST": "unix:///elsewhere.sock"}}))
    assert cli.main(args) == 3  # conflict reported, not overwritten
    capsys.readouterr()

    target.write_text("{broken")
    assert cli.main(args) == 2
    assert "not valid JSON" in capsys.readouterr().err
