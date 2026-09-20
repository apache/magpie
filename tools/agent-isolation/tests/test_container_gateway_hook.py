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

SCRIPT = Path(__file__).parent.parent / "container-gateway-hook.sh"


def run(action: str, cwd: Path, env_extra: dict[str, str] | None = None, payload: dict[str, object] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "MAGPIE_CONTAINER_GATEWAY_DRY_RUN": "1", **(env_extra or {})}
    return subprocess.run(["bash", str(SCRIPT), action], input=json.dumps(payload or {"cwd": str(cwd)}),
                          capture_output=True, text=True, env=env, cwd=cwd, check=False)


def test_start_uses_snapshot_sources(tmp_path: Path) -> None:
    tmp_path = tmp_path.resolve()  # the hook prints physical paths (pwd -P); macOS tmp dirs are symlinked
    src = tmp_path / ".apache-magpie" / "tools" / "container-gateway" / "src" / "container_gateway"
    src.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    done = run("start", tmp_path)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == f"PYTHONPATH={src.parent} python3 -m container_gateway serve --project={tmp_path} --daemon"


def test_start_prefers_env_override_and_appends_args(tmp_path: Path) -> None:
    alt = tmp_path / "alt-src"
    (alt / "container_gateway").mkdir(parents=True)
    done = run("start", tmp_path, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(alt), "MAGPIE_CONTAINER_GATEWAY_ARGS": "--egress require"})
    assert done.stdout.strip().endswith(f"serve --project={tmp_path.resolve()} --daemon --egress require")
    assert f"PYTHONPATH={alt}" in done.stdout


def test_stop_command(tmp_path: Path) -> None:
    src = tmp_path / ".apache-magpie" / "tools" / "container-gateway" / "src" / "container_gateway"
    src.mkdir(parents=True)
    done = run("stop", tmp_path)
    assert done.stdout.strip().endswith(f"stop --project={tmp_path.resolve()}")


def test_no_sources_is_silent_success(tmp_path: Path) -> None:
    done = run("start", tmp_path)
    assert done.returncode == 0 and done.stdout == ""


def test_in_repo_sources_are_ignored(tmp_path: Path) -> None:
    """In-repo sources are never trusted, even when present."""
    (tmp_path / "tools" / "container-gateway" / "src" / "container_gateway").mkdir(parents=True)
    done = run("start", tmp_path)
    assert done.returncode == 0 and done.stdout == ""


def test_user_scope_copy_is_preferred_over_snapshot(tmp_path: Path) -> None:
    """Operator-installed copy in $HOME/.claude/scripts takes precedence over snapshot."""
    tmp_path = tmp_path.resolve()
    # Create both user-scope and snapshot copies
    user_src = tmp_path / ".claude" / "scripts" / "container-gateway" / "src" / "container_gateway"
    user_src.mkdir(parents=True)
    snap_src = tmp_path / ".apache-magpie" / "tools" / "container-gateway" / "src" / "container_gateway"
    snap_src.mkdir(parents=True)
    # Use a fake HOME pointing to tmp_path/.claude/..
    fake_home = tmp_path / ".fake-home"
    fake_home.mkdir()
    (fake_home / ".claude" / "scripts" / "container-gateway" / "src" / "container_gateway").mkdir(parents=True)
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    done = run("start", proj, {"HOME": str(fake_home)})
    assert done.returncode == 0, done.stderr
    # Should use the user-scope path, not the snapshot
    assert f"PYTHONPATH={fake_home}/.claude/scripts/container-gateway/src" in done.stdout


def test_bad_action_exits_zero_with_message(tmp_path: Path) -> None:
    done = run("frobnicate", tmp_path)
    assert done.returncode == 0 and "expected start|stop" in done.stderr
