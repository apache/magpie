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

"""The managed-settings dispatcher runs only the invoking account's own gateway hook.

Managed settings apply to every account on the machine, so the dispatcher must
never run a hook another account could have written.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "container-gateway-dispatch.sh"


def install_hook(home: Path) -> Path:
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    for directory in (home / ".claude", scripts):
        directory.chmod(0o755)
    hook = scripts / "container-gateway-hook.sh"
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    hook.chmod(0o755)
    return hook


def dispatch(home: Path, action: str = "start") -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "MAGPIE_CONTAINER_GATEWAY_DRY_RUN": "1",
        "MAGPIE_GATEWAY_DISPATCH_HOME": str(home),
    }
    return subprocess.run(
        [str(SCRIPT), action],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.parametrize("action", ["start", "stop", "ensure"])
def test_the_invoking_accounts_own_hook_is_run(tmp_path: Path, action: str) -> None:
    hook = install_hook(tmp_path)
    done = dispatch(tmp_path, action)
    assert done.returncode == 0
    assert done.stdout == f"{hook} {action}\n"


@pytest.mark.parametrize("target", ["hook", "scripts", "claude"])
def test_anything_another_account_could_write_is_refused(
    tmp_path: Path, target: str
) -> None:
    hook = install_hook(tmp_path)
    {"hook": hook, "scripts": hook.parent, "claude": hook.parent.parent}[target].chmod(
        0o777
    )
    done = dispatch(tmp_path)
    assert done.returncode == 0
    assert done.stdout == ""
    assert "not owned and writable by" in done.stderr


def test_a_group_writable_home_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    install_hook(home)
    home.chmod(0o775)
    done = dispatch(home)
    assert done.stdout == ""
    assert "not owned and writable by" in done.stderr


def test_a_writable_ancestor_of_the_home_is_refused(tmp_path: Path) -> None:
    parent = tmp_path / "shared"
    home = parent / "home"
    home.mkdir(parents=True)
    install_hook(home)
    parent.chmod(0o777)
    try:
        done = dispatch(home)
    finally:
        parent.chmod(0o755)
    assert done.stdout == ""
    assert "writable by another account" in done.stderr


def test_a_sticky_world_writable_ancestor_is_accepted(tmp_path: Path) -> None:
    parent = tmp_path / "sticky"
    home = parent / "home"
    home.mkdir(parents=True)
    hook = install_hook(home)
    parent.chmod(0o1777)
    try:
        done = dispatch(home)
    finally:
        parent.chmod(0o755)
    assert done.stdout == f"{hook} start\n"


macos_only = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS ACLs via chmod +a"
)


@macos_only
@pytest.mark.parametrize("target", ["hook", "scripts"])
def test_an_acl_letting_another_account_write_is_refused(
    tmp_path: Path, target: str
) -> None:
    hook = install_hook(tmp_path)
    path = hook if target == "hook" else hook.parent
    subprocess.run(
        ["/bin/chmod", "+a", "group:staff allow write,append", str(path)], check=True
    )
    done = dispatch(tmp_path)
    assert done.stdout == ""
    assert "not owned and writable by" in done.stderr


@macos_only
def test_an_acl_is_refused_even_without_a_usable_tmpdir(tmp_path: Path) -> None:
    hook = install_hook(tmp_path)
    subprocess.run(
        ["/bin/chmod", "+a", "group:staff allow write,append", str(hook)], check=True
    )
    env = {
        "PATH": "/usr/bin:/bin",
        "TMPDIR": str(tmp_path / "no-such-dir"),
        "MAGPIE_CONTAINER_GATEWAY_DRY_RUN": "1",
        "MAGPIE_GATEWAY_DISPATCH_HOME": str(tmp_path),
    }
    done = subprocess.run(
        [str(SCRIPT), "start"],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert done.stdout == ""


@macos_only
def test_a_deny_acl_like_the_default_home_one_is_accepted(tmp_path: Path) -> None:
    hook = install_hook(tmp_path)
    subprocess.run(
        ["/bin/chmod", "+a", "group:everyone deny delete", str(tmp_path)], check=True
    )
    done = dispatch(tmp_path)
    assert done.stdout == f"{hook} start\n"


def test_a_symlinked_hook_is_refused(tmp_path: Path) -> None:
    hook = install_hook(tmp_path)
    real = tmp_path / "elsewhere.sh"
    hook.rename(real)
    hook.symlink_to(real)
    done = dispatch(tmp_path)
    assert done.returncode == 0
    assert done.stdout == ""
    assert "is a symlink; replace it with a plain copy" in done.stderr


def test_an_account_without_the_hook_gets_nothing(tmp_path: Path) -> None:
    done = dispatch(tmp_path)
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


def test_a_bad_action_never_fails_the_session(tmp_path: Path) -> None:
    install_hook(tmp_path)
    done = dispatch(tmp_path, "explode")
    assert done.returncode == 0
    assert done.stdout == ""
    assert "expected start|stop|ensure" in done.stderr


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_the_dispatcher_is_executable() -> None:
    assert os.access(SCRIPT, os.X_OK)
