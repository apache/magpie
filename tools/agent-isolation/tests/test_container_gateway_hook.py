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
import shutil
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
    return subprocess.run(["/bin/bash", str(SCRIPT), action], input=json.dumps({"cwd": str(cwd)}),
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
    assert done.stdout.strip() == f"{PYTHON} -I -S {lay.src} container_gateway serve --project={lay.project} --daemon"


def test_stop_command(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    done = run("stop", lay.project, home=lay.home)
    assert done.stdout.strip() == f"{PYTHON} -I -S {lay.src} container_gateway stop --project={lay.project}"


def test_env_override_is_preferred_and_args_appended(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    alt = lay.base / "alt-src"
    (alt / "container_gateway").mkdir(parents=True)
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(alt),
                                      "MAGPIE_CONTAINER_GATEWAY_ARGS": "--egress require"}, home=lay.home)
    assert done.stdout.strip() == f"{PYTHON} -I -S {alt} container_gateway serve --project={lay.project} --daemon --egress require"


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
    assert f" -I -S {lay.src} " in done.stdout


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
    assert f" -I -S {lay.src} " in done.stdout


def test_a_relative_user_scope_grant_resolves_under_dot_claude(tmp_path: Path) -> None:
    """Relative entries in ~/.claude/settings.json resolve against ~/.claude, not the project."""
    lay = Layout(tmp_path)
    alt = lay.home / ".claude" / "shared" / "src"
    (alt / "container_gateway").mkdir(parents=True)
    lay.settings({"sandbox": {"filesystem": {"allowWrite": ["shared"]}}})
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(alt)}, home=lay.home)
    assert "refusing gateway source" in done.stderr
    assert f" -I -S {lay.src} " in done.stdout


def test_helpers_are_not_taken_from_an_inherited_path(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    bin_dir = lay.base / "bin"
    bin_dir.mkdir()
    marker = lay.base / "ran"
    for name in ("jq", "git", "readlink", "dirname"):
        tool = bin_dir / name
        tool.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
        tool.chmod(0o755)
    done = run("start", lay.project, {"PATH": f"{bin_dir}:{os.environ['PATH']}"}, home=lay.home)
    assert not marker.exists()
    assert done.stdout.strip() == f"{PYTHON} -I -S {lay.src} container_gateway serve --project={lay.project} --daemon"


@pytest.mark.parametrize("rel", [".cache/gw", ".local/share/gw"])
def test_override_under_home_cache_or_local_is_refused(tmp_path: Path, rel: str) -> None:
    """Granted to every project by the reference setup, so refused whatever this one grants."""
    lay = Layout(tmp_path)
    alt = lay.home / rel
    (alt / "container_gateway").mkdir(parents=True)
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(alt)}, home=lay.home)
    assert "refusing gateway source" in done.stderr
    assert f" -I -S {lay.src} " in done.stdout


def test_a_symlinked_source_is_judged_by_its_target(tmp_path: Path) -> None:
    lay = Layout(tmp_path, user_copy=False)
    real = lay.home / ".cache" / "gw"
    (real / "container_gateway").mkdir(parents=True)
    lay.src.symlink_to(real)
    done = run("start", lay.project, home=lay.home)
    assert "refusing gateway source" in done.stderr
    assert done.stdout == ""


def test_a_symlink_inside_the_source_tree_is_refused(tmp_path: Path) -> None:
    """A module linked out of the installed copy could point anywhere writable."""
    lay = Layout(tmp_path)
    planted = lay.home / ".cache" / "daemon.py"
    planted.parent.mkdir(parents=True)
    planted.write_text("")
    (lay.src / "container_gateway" / "daemon.py").symlink_to(planted)
    done = run("start", lay.project, home=lay.home)
    assert "refusing gateway source" in done.stderr
    assert done.stdout == ""


def test_a_grant_on_one_file_of_the_source_is_refused(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    module = lay.src / "container_gateway" / "daemon.py"
    module.write_text("")
    lay.settings({"sandbox": {"filesystem": {"allowWrite": [str(module)]}}})
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


def test_a_grant_inside_the_interpreter_prefix_skips_it(tmp_path: Path) -> None:
    """A writable stdlib file would run during the version probe itself."""
    lay = Layout(tmp_path)
    prefix = Path(PYTHON).parent.parent
    lay.settings({"sandbox": {"filesystem": {"allowWrite": [str(prefix / "lib" / "planted")]}}})
    done = run("start", lay.project, home=lay.home)
    assert not done.stdout.startswith(f"{PYTHON} ")


def test_a_stdlib_module_linked_into_a_writable_dir_skips_the_interpreter(tmp_path: Path) -> None:
    """Built from a copy of the running interpreter's layout, so nothing real is touched."""
    lay = Layout(tmp_path)
    real_prefix = Path(PYTHON).parent.parent
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    fake = lay.base / "py"
    (fake / "bin").mkdir(parents=True)
    (fake / "lib" / version).mkdir(parents=True)
    (fake / "lib" / version / "os.py").write_text("")
    planted = lay.home / ".cache" / "sysconfig.py"
    planted.parent.mkdir(parents=True)
    planted.write_text("")
    (fake / "lib" / version / "sysconfig.py").symlink_to(planted)
    shutil.copy2(PYTHON, fake / "bin" / "python3")
    (lay.scripts / "python").write_text(f"{fake / 'bin' / 'python3'}\n")
    done = run("start", lay.project, home=lay.home)
    assert str(fake) not in done.stdout
    assert real_prefix.exists()


def test_a_module_behind_a_linked_stdlib_dir_skips_the_interpreter(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    external = lay.base / "external-stdlib"
    external.mkdir()
    (external / "os.py").write_text("")
    planted = lay.home / ".cache" / "sysconfig.py"
    planted.parent.mkdir(parents=True)
    planted.write_text("")
    (external / "sysconfig.py").symlink_to(planted)
    fake = lay.base / "py"
    (fake / "bin").mkdir(parents=True)
    (fake / "lib").mkdir()
    (fake / "lib" / version).symlink_to(external)
    shutil.copy2(PYTHON, fake / "bin" / "python3")
    (lay.scripts / "python").write_text(f"{fake / 'bin' / 'python3'}\n")
    done = run("start", lay.project, home=lay.home)
    assert str(fake) not in done.stdout


def test_a_linked_worktree_counts_the_main_checkout_grants(tmp_path: Path) -> None:
    """Claude Code reads the main checkout's settings in a linked worktree."""
    lay = Layout(tmp_path)
    git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "-C", str(lay.project), "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "init"],
                   check=True, env=git_env)
    worktree = lay.base / "wt"
    subprocess.run(["git", "-C", str(lay.project), "worktree", "add", "-q", str(worktree)], check=True)
    shared = lay.base / "shared"
    (shared / "src" / "container_gateway").mkdir(parents=True)
    (lay.project / ".claude").mkdir()
    (lay.project / ".claude" / "settings.local.json").write_text(
        json.dumps({"sandbox": {"filesystem": {"allowWrite": [str(shared)]}}}))
    done = run("start", worktree, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(shared / "src")}, home=lay.home)
    assert "refusing gateway source" in done.stderr
    assert f" -I -S {lay.src} " in done.stdout


@pytest.mark.parametrize("rule", ["Edit({shared}/**)", "Write(/{shared}/**)", "Edit"])
def test_an_edit_allow_rule_counts_as_a_write_grant(tmp_path: Path, rule: str) -> None:
    """Claude Code merges Edit(...) allow rules into the sandbox's write access."""
    lay = Layout(tmp_path)
    shared = lay.base / "shared"
    (shared / "src" / "container_gateway").mkdir(parents=True)
    lay.settings({"permissions": {"allow": [rule.format(shared=shared)]}})
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(shared / "src")}, home=lay.home)
    assert "refusing gateway source" in done.stderr
    if rule == "Edit":  # every file writable: nothing is trusted
        assert done.stdout == ""
    else:
        assert f" -I -S {lay.src} " in done.stdout


def test_an_unconfirmed_worktree_link_refuses_to_start(tmp_path: Path) -> None:
    """The worktree's own .git file is writable; a main checkout it names must point back."""
    lay = Layout(tmp_path)
    fake_common = lay.base / "elsewhere" / ".git"
    (fake_common / "worktrees" / "wt").mkdir(parents=True)
    worktree = lay.base / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {fake_common / 'worktrees' / 'wt'}\n")
    done = run("start", worktree, home=lay.home)
    assert done.returncode == 0
    assert done.stdout == ""


def test_the_interpreter_runs_by_its_canonical_path(tmp_path: Path) -> None:
    """A symlink on the way (here a writable one) cannot be swapped after the check."""
    lay = Layout(tmp_path)
    link_dir = lay.base / "opt" / "bin"
    link_dir.parent.mkdir(parents=True)
    hop = lay.home / ".cache" / "python-link"
    hop.parent.mkdir(parents=True)
    hop.symlink_to(Path(PYTHON).parent)
    link_dir.symlink_to(hop)
    (lay.scripts / "python").write_text(f"{link_dir / Path(PYTHON).name}\n")
    done = run("start", lay.project, home=lay.home)
    assert str(link_dir) not in done.stdout and str(hop) not in done.stdout


def test_a_relative_source_override_is_refused(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    (lay.project / "gw" / "container_gateway").mkdir(parents=True)
    done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": "gw"}, home=lay.home)
    assert "not an absolute path" in done.stderr
    assert f" -I -S {lay.src} " in done.stdout


def test_a_virtualenv_pin_is_never_run(tmp_path: Path) -> None:
    """Its base runtime could live anywhere, ~/.local/share/uv included."""
    lay = Layout(tmp_path)
    venv = lay.base / "venv"
    subprocess.run([PYTHON, "-m", "venv", "--without-pip", "--copies", str(venv)], check=True)
    (lay.scripts / "python").write_text(f"{venv / 'bin' / 'python3'}\n")
    done = run("start", lay.project, home=lay.home)
    assert str(venv) not in done.stdout


def test_a_pin_without_a_standard_library_is_never_executed(tmp_path: Path) -> None:
    """A launcher stub (macOS /usr/bin/python3) execs another interpreter; it is judged unrun."""
    lay = Layout(tmp_path)
    marker = lay.base / "ran"
    stub = lay.base / "stub" / "bin" / "python3"
    stub.parent.mkdir(parents=True)
    stub.write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
    stub.chmod(0o755)
    (lay.scripts / "python").write_text(f"{stub}\n")
    done = run("start", lay.project, home=lay.home)
    assert not marker.exists()
    assert str(stub) not in done.stdout


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
