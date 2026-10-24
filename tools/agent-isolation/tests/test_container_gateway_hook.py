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

"""The session hook finds the project, finds the gateway, and never blocks a session.

It runs outside the sandbox, so it must never execute an interpreter or a source
tree that a sandboxed command could have written.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "container-gateway-hook.sh"
PYTHON = os.path.realpath(sys.executable)  # a venv under the checkout would itself be refused
SANDBOX_SCRATCH = ("/tmp/claude", "/private/tmp/claude")


def run(action: str, cwd: Path, env_extra: dict[str, str] | None = None, home: Path | None = None,
        dry_run: bool = True) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_TMPDIR"}
    if dry_run:
        env["MAGPIE_CONTAINER_GATEWAY_DRY_RUN"] = "1"
    if home is not None:
        env["HOME"] = str(home)
    env.update(env_extra or {})
    return subprocess.run(["bash", str(SCRIPT), action], input=json.dumps({"cwd": str(cwd)}),
                          capture_output=True, text=True, env=env, cwd=cwd, check=False)


class Layout:
    """A fake $HOME holding the operator install and an interpreter pin, plus a project."""

    def __init__(self, tmp_path: Path, *, user_copy: bool = True, pin: str | None = PYTHON) -> None:
        base = tmp_path.resolve()  # the hook prints physical paths; macOS tmp dirs are symlinked
        if str(base).startswith(SANDBOX_SCRATCH):
            pytest.skip("the sandbox's scratch directory is itself a writable root; run outside the sandbox")
        self.base = base
        self.home = base / "home"
        self.scripts = self.home / ".claude" / "scripts" / "container-gateway"
        self.src = self.scripts / "src"
        if user_copy:
            (self.src / "container_gateway").mkdir(parents=True)
        self.scripts.mkdir(parents=True, exist_ok=True)
        if pin is not None:
            (self.scripts / "python").write_text(pin + "\n")
        self.project = base / "proj"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)

    def settings(self, data: dict[str, object]) -> None:
        (self.home / ".claude" / "settings.json").write_text(json.dumps(data))


def test_start_runs_the_pinned_interpreter_isolated(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    done = run("start", lay.project, home=lay.home)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == f"{PYTHON} -I {lay.src} container_gateway serve --project={lay.project} --daemon"


def test_stop_command(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    done = run("stop", lay.project, home=lay.home)
    assert done.stdout.strip() == f"{PYTHON} -I {lay.src} container_gateway stop --project={lay.project}"


def test_env_override_is_preferred_and_args_appended(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    alt = lay.base / "alt-src"
    (alt / "container_gateway").mkdir(parents=True)
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(alt),
                                      "MAGPIE_CONTAINER_GATEWAY_ARGS": "--egress require"}, home=lay.home)
    assert done.stdout.strip() == f"{PYTHON} -I {alt} container_gateway serve --project={lay.project} --daemon --egress require"


def test_no_sources_is_silent_success(tmp_path: Path) -> None:
    lay = Layout(tmp_path, user_copy=False)
    done = run("start", lay.project, home=lay.home)
    assert done.returncode == 0 and done.stdout == ""


def test_bad_action_exits_zero_with_message(tmp_path: Path) -> None:
    done = run("frobnicate", tmp_path, home=tmp_path)
    assert done.returncode == 0 and "expected start|stop" in done.stderr


# --- sources: never from a sandbox-writable directory ---


@pytest.mark.parametrize("rel", ["tools/container-gateway/src", ".apache-magpie/tools/container-gateway/src"])
def test_in_repo_sources_are_never_used(tmp_path: Path, rel: str) -> None:
    """The project root is always sandbox-writable, snapshot included."""
    lay = Layout(tmp_path, user_copy=False)
    (lay.project / rel / "container_gateway").mkdir(parents=True)
    done = run("start", lay.project, home=lay.home)
    assert done.returncode == 0 and done.stdout == ""


def test_override_inside_the_project_is_refused(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    inside = lay.project / "tools" / "container-gateway" / "src"
    (inside / "container_gateway").mkdir(parents=True)
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(inside)}, home=lay.home)
    assert "refusing gateway source" in done.stderr
    assert f" -I {lay.src} " in done.stdout


@pytest.mark.parametrize("key", ["allowWrite", "additionalDirectories"])
def test_override_under_a_granted_directory_is_refused(tmp_path: Path, key: str) -> None:
    lay = Layout(tmp_path)
    shared = lay.base / "shared"
    (shared / "src" / "container_gateway").mkdir(parents=True)
    grant = ({"sandbox": {"filesystem": {"allowWrite": [f"{shared}/**"]}}} if key == "allowWrite"
             else {"permissions": {"additionalDirectories": [str(shared)]}})
    lay.settings(grant)
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(shared / "src")}, home=lay.home)
    assert "refusing gateway source" in done.stderr
    assert f" -I {lay.src} " in done.stdout


@pytest.mark.parametrize("rel", [".cache/gw", ".local/share/gw"])
def test_override_under_home_cache_or_local_is_refused(tmp_path: Path, rel: str) -> None:
    """Granted to every project by the reference setup, so refused whatever this one grants."""
    lay = Layout(tmp_path)
    alt = lay.home / rel
    (alt / "container_gateway").mkdir(parents=True)
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(alt)}, home=lay.home)
    assert "refusing gateway source" in done.stderr
    assert f" -I {lay.src} " in done.stdout


def test_a_symlinked_source_is_judged_by_its_target(tmp_path: Path) -> None:
    lay = Layout(tmp_path, user_copy=False)
    real = lay.home / ".cache" / "gw"
    (real / "container_gateway").mkdir(parents=True)
    lay.src.symlink_to(real)
    done = run("start", lay.project, home=lay.home)
    assert "refusing gateway source" in done.stderr
    assert done.stdout == ""


# --- the interpreter: never from PATH, never from a sandbox-writable directory ---


def test_a_python3_on_path_is_not_used(tmp_path: Path) -> None:
    lay = Layout(tmp_path, pin=None)
    bin_dir = lay.project / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "python3"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    done = run("start", lay.project, {"PATH": f"{bin_dir}:{os.environ['PATH']}"}, home=lay.home)
    assert str(fake) not in done.stdout + done.stderr


@pytest.mark.parametrize("rel", [".local/share/uv/python/bin/python3", ".cache/py/python3"])
def test_a_pin_under_a_writable_root_is_skipped(tmp_path: Path, rel: str) -> None:
    """A uv-managed python3 under ~/.local/share/uv is writable from the sandbox."""
    lay = Layout(tmp_path)
    planted = lay.home / rel
    planted.parent.mkdir(parents=True)
    planted.symlink_to(PYTHON)  # its target is fine; the link itself can be re-pointed
    (lay.scripts / "python").write_text(f"{planted}\n")
    done = run("start", lay.project, home=lay.home)
    assert str(planted) not in done.stdout


def test_a_pin_inside_the_project_is_skipped(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    planted = lay.project / ".venv" / "bin" / "python3"
    planted.parent.mkdir(parents=True)
    planted.symlink_to(PYTHON)
    (lay.scripts / "python").write_text(f"{planted}\n")
    done = run("start", lay.project, home=lay.home)
    assert str(planted) not in done.stdout


def test_isolated_mode_ignores_pythonpath_and_the_project(tmp_path: Path) -> None:
    """A real run: neither PYTHONPATH nor a package in the project reaches sys.path."""
    lay = Layout(tmp_path)
    (lay.src / "container_gateway" / "__main__.py").write_text(
        "import json, sys\n"
        "project = next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--project='))\n"
        "open(project + '/out.json', 'w').write(json.dumps({'path': sys.path, 'file': __file__, 'argv': sys.argv[1:]}))\n")
    evil = lay.base / "evil"
    evil.mkdir()
    (lay.project / "container_gateway").mkdir()
    (lay.project / "container_gateway" / "__main__.py").write_text("raise SystemExit('project code ran')\n")
    done = run("stop", lay.project, {"PYTHONPATH": str(evil)}, home=lay.home, dry_run=False)
    assert done.returncode == 0, done.stderr
    out = json.loads((lay.project / "out.json").read_text())
    assert out["file"].startswith(str(lay.src))
    assert out["argv"] == ["stop", f"--project={lay.project}"]
    assert str(evil) not in out["path"]
    assert str(lay.project) not in out["path"] and "" not in out["path"]


# --- MAGPIE_CONTAINER_GATEWAY_ARGS is allow-listed ---


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
    lay = Layout(tmp_path)
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_ARGS": args}, home=lay.home)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith(f"serve --project={lay.project} --daemon")
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
    lay = Layout(tmp_path)
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_ARGS": args}, home=lay.home)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith(f"--daemon {args}")
    assert done.stderr == ""
