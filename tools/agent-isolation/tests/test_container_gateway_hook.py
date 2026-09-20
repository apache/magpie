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

"""The session hook finds the project, finds the gateway, and never blocks a session."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "container-gateway-hook.sh"


def run(action: str, cwd: Path, env_extra: dict[str, str] | None = None, payload: dict[str, object] | None = None, home: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "MAGPIE_CONTAINER_GATEWAY_DRY_RUN": "1"}
    if home is not None:
        env["HOME"] = str(home)
    env.update(env_extra or {})
    return subprocess.run(["bash", str(SCRIPT), action], input=json.dumps(payload or {"cwd": str(cwd)}),
                          capture_output=True, text=True, env=env, cwd=cwd, check=False)


def test_start_uses_snapshot_sources(tmp_path: Path) -> None:
    tmp_path = tmp_path.resolve()  # the hook prints physical paths (pwd -P); macOS tmp dirs are symlinked
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    src = tmp_path / ".apache-magpie" / "tools" / "container-gateway" / "src" / "container_gateway"
    src.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    done = run("start", tmp_path, home=fake_home)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == f"PYTHONPATH={src.parent} python3 -m container_gateway serve --project={tmp_path} --daemon"


def test_start_prefers_env_override_and_appends_args(tmp_path: Path) -> None:
    tmp_path = tmp_path.resolve()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    alt = tmp_path / "alt-src"
    (alt / "container_gateway").mkdir(parents=True)
    done = run("start", tmp_path, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(alt), "MAGPIE_CONTAINER_GATEWAY_ARGS": "--egress require"}, home=fake_home)
    assert done.stdout.strip().endswith(f"serve --project={tmp_path} --daemon --egress require")
    assert f"PYTHONPATH={alt}" in done.stdout


def test_stop_command(tmp_path: Path) -> None:
    tmp_path = tmp_path.resolve()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    src = tmp_path / ".apache-magpie" / "tools" / "container-gateway" / "src" / "container_gateway"
    src.mkdir(parents=True)
    done = run("stop", tmp_path, home=fake_home)
    assert done.stdout.strip().endswith(f"stop --project={tmp_path}")


def test_no_sources_is_silent_success(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    done = run("start", tmp_path, home=fake_home)
    assert done.returncode == 0 and done.stdout == ""


def test_in_repo_sources_are_ignored(tmp_path: Path) -> None:
    """In-repo sources are never trusted, even when present."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (tmp_path / "tools" / "container-gateway" / "src" / "container_gateway").mkdir(parents=True)
    done = run("start", tmp_path, home=fake_home)
    assert done.returncode == 0 and done.stdout == ""


def test_user_scope_copy_is_preferred_over_snapshot(tmp_path: Path) -> None:
    """Operator-installed copy in $HOME/.claude/scripts takes precedence over snapshot."""
    tmp_path = tmp_path.resolve()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    # Create snapshot under proj/.apache-magpie
    snap_src = proj / ".apache-magpie" / "tools" / "container-gateway" / "src" / "container_gateway"
    snap_src.mkdir(parents=True)
    # Create HOME copy under fake_home/.claude/scripts
    user_src = fake_home / ".claude" / "scripts" / "container-gateway" / "src" / "container_gateway"
    user_src.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    done = run("start", proj, home=fake_home)
    assert done.returncode == 0, done.stderr
    # Should use the user-scope path, not the snapshot
    assert f"PYTHONPATH={fake_home}/.claude/scripts/container-gateway/src" in done.stdout


def test_snapshot_used_when_user_copy_absent(tmp_path: Path) -> None:
    """When only the snapshot exists, it is used."""
    tmp_path = tmp_path.resolve()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    # Create only snapshot under proj/.apache-magpie
    snap_src = proj / ".apache-magpie" / "tools" / "container-gateway" / "src" / "container_gateway"
    snap_src.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    done = run("start", proj, home=fake_home)
    assert done.returncode == 0, done.stderr
    # Should use the snapshot path
    assert f"PYTHONPATH={snap_src.parent}" in done.stdout


def test_bad_action_exits_zero_with_message(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    done = run("frobnicate", tmp_path, home=fake_home)
    assert done.returncode == 0 and "expected start|stop" in done.stderr


# --- I5: the inherited environment is not part of the trust model ---


def _project_with_snapshot(tmp_path: Path) -> tuple[Path, Path, Path]:
    tmp_path = tmp_path.resolve()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    src = tmp_path / ".apache-magpie" / "tools" / "container-gateway" / "src"
    (src / "container_gateway").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path, fake_home, src


def test_inherited_pythonpath_is_replaced_not_extended(tmp_path: Path) -> None:
    """A repo-settable PYTHONPATH could shadow a stdlib module the package imports."""
    project, fake_home, src = _project_with_snapshot(tmp_path)
    shadow = project / "evil"
    shadow.mkdir()
    done = run("start", project, {"PYTHONPATH": str(shadow)}, home=fake_home)
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith(f"PYTHONPATH={src} ")
    assert str(shadow) not in done.stdout


@pytest.mark.parametrize(
    "args",
    [
        "--extra-bind-root /",
        "--extra-bind-root=/Users",
        "--project /elsewhere",
        "--run-dir /tmp/x",
        "--egress require --extra-bind-root /",
        "--pid-file /tmp/x.pid",
        "not-a-flag",
        "--egress",  # a flag whose value never arrives
    ],
)
def test_unvetted_extra_args_are_ignored_whole(tmp_path: Path, args: str) -> None:
    project, fake_home, _ = _project_with_snapshot(tmp_path)
    done = run("start", project, {"MAGPIE_CONTAINER_GATEWAY_ARGS": args}, home=fake_home)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith(f"serve --project={project} --daemon")
    assert "ignoring MAGPIE_CONTAINER_GATEWAY_ARGS" in done.stderr


@pytest.mark.parametrize(
    "args",
    [
        "--egress require",
        "--egress=require",
        "--egress-port 8899",
        "--egress-host 10.88.0.1",
        "--backend podman --log-level DEBUG",
        "--idle-timeout 60 --backend-timeout 30",
    ],
)
def test_vetted_extra_args_are_passed_through(tmp_path: Path, args: str) -> None:
    project, fake_home, _ = _project_with_snapshot(tmp_path)
    done = run("start", project, {"MAGPIE_CONTAINER_GATEWAY_ARGS": args}, home=fake_home)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith(f"--daemon {args}")
    assert done.stderr == ""
