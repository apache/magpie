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
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "container-gateway-hook.sh"
PYTHON = os.path.realpath(sys.executable)  # a venv under the checkout would itself be refused
SANDBOX_SCRATCH = ("/tmp/claude", "/private/tmp/claude")


def run(action: str, cwd: Path, env_extra: dict[str, str] | None = None, home: Path | None = None,
        dry_run: bool = True, payload: str | None = None) -> subprocess.CompletedProcess[str]:
    # The harness under test sets CLAUDE_PROJECT_DIR on hooks; never inherit the one running these tests.
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_TMPDIR", "CLAUDE_PROJECT_DIR")}
    if dry_run:
        env["MAGPIE_CONTAINER_GATEWAY_DRY_RUN"] = "1"
    if home is not None:
        env["HOME"] = str(home)
        # Worktree records go under the fake home, never the account's real one.
        env["MAGPIE_CONTAINER_GATEWAY_STATE_DIR"] = str(home / ".claude" / "magpie-gateway")
    env.update(env_extra or {})
    if payload is None:
        payload = json.dumps({"cwd": str(cwd)})
    return subprocess.run(["/bin/bash", str(SCRIPT), action], input=payload,
                          capture_output=True, text=True, env=env, cwd=cwd, check=False, timeout=60)


def bash_payload(cwd: Path, command: str) -> str:
    """What Claude Code hands a PreToolUse hook for a Bash call."""
    return json.dumps({"cwd": str(cwd), "hook_event_name": "PreToolUse", "tool_name": "Bash",
                       "tool_input": {"command": command}})


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


def _fake_runtime(lay: Layout, *, link_stdlib_to: Path | None = None) -> tuple[Path, Path, Path]:
    """<prefix>/bin/python3 + <prefix>/lib/python3.X, pinned; returns (prefix, stdlib, marker).

    The "interpreter" only touches the marker, so the marker exists exactly when the
    hook trusted the layout far enough to run it.
    """
    fake = lay.base / "py"
    marker = lay.base / "interpreter-ran"
    (fake / "bin").mkdir(parents=True)
    (fake / "lib").mkdir()
    stdlib = fake / "lib" / "python3.13"
    if link_stdlib_to is None:
        stdlib.mkdir()
    else:
        stdlib.symlink_to(link_stdlib_to)
    (stdlib / "os.py").write_text("")
    interpreter = fake / "bin" / "python3"
    interpreter.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    interpreter.chmod(0o755)
    (lay.scripts / "python").write_text(f"{interpreter}\n")
    return fake, stdlib, marker


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
    assert done.returncode == 0 and "expected start|stop|ensure" in done.stderr


# --- ensure: start on demand before a container command ---


def ensure(lay: Layout, command: str, *, cwd: Path | None = None, project_dir: str | None = None,
           env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """`ensure` as Claude Code runs it: the session's project in CLAUDE_PROJECT_DIR, the agent's cwd in the payload."""
    where = cwd or lay.project
    env = {"CLAUDE_PROJECT_DIR": str(lay.project) if project_dir is None else project_dir, **(env_extra or {})}
    return run("ensure", where, env, home=lay.home, payload=bash_payload(where, command))


def _serve(lay: Layout) -> str:
    return f"{PYTHON} -I -S {lay.src} container_gateway serve --project={lay.project} --daemon"


@pytest.mark.parametrize("command", [
    "docker ps",
    "podman run --rm alpine:3 true",
    "cd sub && docker compose up -d",
    "/usr/local/bin/docker version",
    "docker-compose up",
    "FOO=1 podman-compose build",
    "make test; docker run x",
    "(docker info)",
])
def test_ensure_starts_the_gateway_before_a_container_command(tmp_path: Path, command: str) -> None:
    lay = Layout(tmp_path)
    done = ensure(lay, command)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == _serve(lay)


@pytest.mark.parametrize("command", [
    "ls -la",
    "git log --oneline",
    "cat Dockerfile",
    "grep -r dockerfile .",
    "vim docker.md",
    "./mydocker run",
    "rm podman_notes.txt",
])
def test_ensure_ignores_other_commands(tmp_path: Path, command: str) -> None:
    lay = Layout(tmp_path)
    done = ensure(lay, command)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""


@pytest.mark.parametrize("payload", ["", "not json", json.dumps({"tool_input": None}), json.dumps([1, 2])])
def test_ensure_ignores_a_malformed_payload(tmp_path: Path, payload: str) -> None:
    lay = Layout(tmp_path)
    done = run("ensure", lay.project, {"CLAUDE_PROJECT_DIR": str(lay.project)}, home=lay.home, payload=payload)
    assert done.returncode == 0 and done.stdout == ""


def test_ensure_judges_the_session_project_not_the_cwd(tmp_path: Path) -> None:
    """The payload cwd follows `cd`; CLAUDE_PROJECT_DIR is where the session started."""
    lay = Layout(tmp_path)
    elsewhere = lay.base / "other"
    elsewhere.mkdir()
    subprocess.run(["git", "init", "-q", str(elsewhere)], check=True)
    done = ensure(lay, "docker ps", cwd=elsewhere)
    assert done.stdout.strip() == _serve(lay)


def test_ensure_counts_the_session_project_grants_after_a_cd(tmp_path: Path) -> None:
    """A source the session project makes writable stays refused after `cd` into a directory without that grant."""
    lay = Layout(tmp_path)
    (lay.project / ".claude").mkdir()
    (lay.project / ".claude" / "settings.local.json").write_text(
        json.dumps({"sandbox": {"filesystem": {"allowWrite": [str(lay.src)]}}}))
    elsewhere = lay.base / "other"
    elsewhere.mkdir()
    subprocess.run(["git", "init", "-q", str(elsewhere)], check=True)
    done = ensure(lay, "docker ps", cwd=elsewhere)
    assert done.stdout == "" and "refusing gateway source" in done.stderr


@pytest.mark.parametrize("project_dir", ["", "relative/dir", "proj"])
def test_ensure_without_an_absolute_project_dir_does_nothing(tmp_path: Path, project_dir: str) -> None:
    lay = Layout(tmp_path)
    done = ensure(lay, "docker ps", project_dir=project_dir)
    assert done.returncode == 0 and done.stdout == ""


def _nested_repo(lay: Layout) -> Path:
    nested = lay.project / "vendor" / "nested"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(nested)], check=True)
    return nested


def test_start_judges_the_session_project_dir_over_the_payload_cwd(tmp_path: Path) -> None:
    """SessionStart after a compaction carries the agent's current cwd; the session project is what counts."""
    lay = Layout(tmp_path)
    nested = _nested_repo(lay)
    done = run("start", nested, {"CLAUDE_PROJECT_DIR": str(lay.project)}, home=lay.home)
    assert done.stdout.strip() == _serve(lay)


@pytest.mark.parametrize("action", ["start", "stop"])
def test_start_and_stop_count_the_session_project_grants_from_a_nested_repo(tmp_path: Path, action: str) -> None:
    lay = Layout(tmp_path)
    (lay.project / ".claude").mkdir()
    (lay.project / ".claude" / "settings.json").write_text(
        json.dumps({"sandbox": {"filesystem": {"allowWrite": [str(lay.src)]}}}))
    nested = _nested_repo(lay)
    done = run(action, nested, {"CLAUDE_PROJECT_DIR": str(lay.project)}, home=lay.home)
    assert done.stdout == "" and "refusing gateway source" in done.stderr


def test_the_payload_cwd_grants_are_counted_too(tmp_path: Path) -> None:
    """Settings in the directory the agent is in can only make the hook refuse more."""
    lay = Layout(tmp_path)
    elsewhere = lay.base / "other"
    (elsewhere / ".claude").mkdir(parents=True)
    (elsewhere / ".claude" / "settings.json").write_text(
        json.dumps({"sandbox": {"filesystem": {"allowWrite": [str(lay.src)]}}}))
    done = ensure(lay, "docker ps", cwd=elsewhere)
    assert done.stdout == "" and "refusing gateway source" in done.stderr


def test_start_falls_back_to_the_payload_cwd_without_a_project_dir(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    done = run("start", lay.project, home=lay.home)
    assert done.stdout.strip() == _serve(lay)


def test_ensure_runs_every_start_check(tmp_path: Path) -> None:
    """On demand opens no new path: a source the start path refuses stays refused."""
    lay = Layout(tmp_path, user_copy=False)
    (lay.project / "tools/container-gateway/src/container_gateway").mkdir(parents=True)
    done = ensure(lay, "docker ps")
    assert done.returncode == 0 and done.stdout == ""


def test_ensure_passes_vetted_extra_args(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    done = ensure(lay, "docker ps", env_extra={"MAGPIE_CONTAINER_GATEWAY_ARGS": "--egress require"})
    assert done.stdout.strip() == _serve(lay) + " --egress require"


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


@pytest.mark.parametrize("rel", [".local/share/uv/tools/x/bin/python3", ".local/bin/python3", ".cache/py/python3"])
def test_a_pin_under_a_writable_root_is_skipped(tmp_path: Path, rel: str) -> None:
    """~/.local and ~/.cache are refused outside uv's managed interpreters."""
    lay = Layout(tmp_path)
    planted = lay.home / rel
    planted.parent.mkdir(parents=True)
    planted.symlink_to(PYTHON)  # its target is fine; the link itself can be re-pointed
    (lay.scripts / "python").write_text(f"{planted}\n")
    done = run("start", lay.project, home=lay.home)
    assert str(planted) not in done.stdout


def _uv_runtime(lay: Layout) -> tuple[Path, Path]:
    """A uv-managed CPython layout under ~/.local/share/uv/python; returns (interpreter, marker)."""
    prefix = lay.home / ".local" / "share" / "uv" / "python" / "cpython-3.13.7-linux-x86_64-gnu"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "lib" / "python3.13").mkdir(parents=True)
    (prefix / "lib" / "python3.13" / "os.py").write_text("")
    marker = lay.base / "uv-interpreter-ran"
    interpreter = prefix / "bin" / "python3.13"
    interpreter.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    interpreter.chmod(0o755)
    return interpreter, marker


def test_a_uv_managed_interpreter_is_trusted(tmp_path: Path) -> None:
    """~/.local/share/uv is read-only to the sandbox in the reference setup."""
    lay = Layout(tmp_path)
    interpreter, marker = _uv_runtime(lay)
    (lay.scripts / "python").write_text(f"{interpreter}\n")
    run("start", lay.project, home=lay.home)
    assert marker.exists()  # trusted far enough to run its version probe


def test_a_symlinked_uv_python_dir_loses_the_exemption(tmp_path: Path) -> None:
    """A linked ~/.local/share/uv/python could point anywhere, ~/.cache included."""
    lay = Layout(tmp_path)
    interpreter, marker = _uv_runtime(lay)
    uv_python = lay.home / ".local" / "share" / "uv" / "python"
    real = lay.home / ".local" / "share" / "elsewhere"
    uv_python.rename(real)
    uv_python.symlink_to(real)
    (lay.scripts / "python").write_text(f"{interpreter}\n")
    run("start", lay.project, home=lay.home)
    assert not marker.exists()


@pytest.mark.parametrize("grant", ["~/.local/share/uv", "~/.local/share/uv/python", "~/.local"])
def test_a_uv_managed_interpreter_under_a_grant_is_refused(tmp_path: Path, grant: str) -> None:
    lay = Layout(tmp_path)
    interpreter, marker = _uv_runtime(lay)
    (lay.scripts / "python").write_text(f"{interpreter}\n")
    lay.settings({"sandbox": {"filesystem": {"allowWrite": [grant]}}})
    run("start", lay.project, home=lay.home)
    assert not marker.exists()


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
    lay = Layout(tmp_path)
    _, stdlib, marker = _fake_runtime(lay)
    planted = lay.home / ".cache" / "sysconfig.py"
    planted.parent.mkdir(parents=True)
    planted.write_text("")
    (stdlib / "sysconfig.py").symlink_to(planted)
    run("start", lay.project, home=lay.home)
    assert not marker.exists()


def test_a_linked_stdlib_dir_skips_the_interpreter(tmp_path: Path) -> None:
    """lib/python3.X must be a real directory: a link could be re-pointed through any hop."""
    lay = Layout(tmp_path)
    external = lay.base / "external-stdlib"
    external.mkdir()
    _, _, marker = _fake_runtime(lay, link_stdlib_to=external)
    run("start", lay.project, home=lay.home)
    assert not marker.exists()


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
    if rule == "Edit":  # every file writable, system locations included: nothing is trusted
        assert done.stdout == ""
        assert "system location" in done.stderr
    else:
        assert "refusing gateway source" in done.stderr
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


def test_a_stdlib_link_that_stays_in_the_prefix_is_accepted(tmp_path: Path) -> None:
    """Homebrew's config-3.X links point back into the prefix; site-packages is never loaded."""
    lay = Layout(tmp_path)
    fake, stdlib, marker = _fake_runtime(lay)
    (fake / "Python").write_text("")
    (stdlib / "config").mkdir()
    (stdlib / "config" / "libpython.dylib").symlink_to("../../../Python")
    (stdlib / "site-packages").symlink_to(lay.home / ".cache")
    run("start", lay.project, home=lay.home)
    assert marker.exists()  # trusted far enough to run its version probe


def test_a_stdlib_link_into_a_system_location_is_accepted(tmp_path: Path) -> None:
    """Debian's /usr/lib/python3.X/sitecustomize.py links into /etc, which no grant may cover."""
    lay = Layout(tmp_path)
    _, stdlib, marker = _fake_runtime(lay)
    (stdlib / "sitecustomize.py").symlink_to("/etc/hosts")
    run("start", lay.project, home=lay.home)
    assert marker.exists()  # trusted far enough to run its version probe


def test_a_symlinked_component_routing_through_a_writable_dir_is_refused(tmp_path: Path) -> None:
    """prefix/x -> ~/.cache/h -> /etc: inside the prefix by name, re-pointable in fact."""
    lay = Layout(tmp_path)
    fake, stdlib, marker = _fake_runtime(lay)
    hop = lay.home / ".cache" / "h"
    hop.parent.mkdir(parents=True)
    hop.symlink_to("/etc")
    (fake / "x").symlink_to(hop)
    (stdlib / "sitecustomize.py").symlink_to("../../x/hosts")
    run("start", lay.project, home=lay.home)
    assert not marker.exists()


def test_a_stdlib_link_hopping_out_and_back_is_refused(tmp_path: Path) -> None:
    """Out through a re-pointable directory, back into the prefix: lexically it leaves."""
    lay = Layout(tmp_path)
    _, stdlib, marker = _fake_runtime(lay)
    (stdlib / "real_sysconfig.py").write_text("")
    hop = lay.home / ".cache" / "hop"
    hop.parent.mkdir(parents=True)
    hop.symlink_to(stdlib)
    (stdlib / "sysconfig.py").symlink_to(hop / "real_sysconfig.py")
    run("start", lay.project, home=lay.home)
    assert not marker.exists()


def test_a_stdlib_link_through_a_writable_dotdot_is_refused(tmp_path: Path) -> None:
    """Folding `..` first would hide the writable hop; each step must stay inside."""
    lay = Layout(tmp_path)
    fake, stdlib, marker = _fake_runtime(lay)
    (stdlib / "safe.py").write_text("")
    hop = lay.home / ".cache" / "hop"
    hop.mkdir(parents=True)
    ups = "/".join([".."] * len(hop.relative_to("/").parts))
    (stdlib / "sysconfig.py").symlink_to(f"{hop}/{ups}{stdlib}/safe.py")
    run("start", lay.project, home=lay.home)
    assert not marker.exists()


@pytest.mark.parametrize("grant", ["/opt/homebrew/opt/openssl@3", "/usr/local", "/opt"])
def test_a_grant_over_a_system_location_refuses_to_start(tmp_path: Path, grant: str) -> None:
    """Native libraries (Homebrew's OpenSSL for _ssl) live there, beyond the prefix checks."""
    lay = Layout(tmp_path)
    lay.settings({"sandbox": {"filesystem": {"allowWrite": [grant]}}})
    done = run("start", lay.project, home=lay.home)
    assert done.stdout == ""
    assert "system location" in done.stderr


def test_a_grant_with_dotdot_refuses_everything(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    lay.settings({"sandbox": {"filesystem": {"allowWrite": ["../elsewhere"]}}})
    done = run("start", lay.project, home=lay.home)
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


def test_an_inherited_git_work_tree_cannot_move_the_project_root(tmp_path: Path) -> None:
    """GIT_DIR / GIT_WORK_TREE from the session environment would make git report
    another toplevel, leaving the real project uncounted as writable."""
    lay = Layout(tmp_path)
    planted = lay.project / "gw"
    (planted / "container_gateway").mkdir(parents=True)
    elsewhere = lay.base / "elsewhere"
    elsewhere.mkdir()
    done = run(
        "start",
        lay.project,
        {
            "GIT_DIR": str(lay.project / ".git"),
            "GIT_WORK_TREE": str(elsewhere),
            "MAGPIE_CONTAINER_GATEWAY_SRC": str(planted),
        },
        home=lay.home,
    )
    assert str(planted) not in done.stdout
    assert "refusing gateway source" in done.stderr


def test_a_core_worktree_outside_the_cwd_refuses_to_start(tmp_path: Path) -> None:
    """`.git/config` is sandbox-writable; a core.worktree pointing elsewhere must not
    turn the session's own directory into a non-writable one."""
    lay = Layout(tmp_path)
    elsewhere = lay.base / "elsewhere"
    elsewhere.mkdir()
    subprocess.run(["git", "-C", str(lay.project), "config", "core.worktree", str(elsewhere)], check=True)
    done = run("start", lay.project, home=lay.home)
    assert done.returncode == 0
    assert done.stdout == ""
    assert "does not contain" in done.stderr


def test_a_redirected_home_does_not_hide_the_account_cache(tmp_path: Path) -> None:
    """With $HOME pointed elsewhere, the account's real ~/.cache is still a writable root."""
    import pwd
    import shutil
    import tempfile

    account_cache = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".cache"
    if not os.access(account_cache, os.W_OK):
        pytest.skip("the account's ~/.cache is not writable here")
    lay = Layout(tmp_path)
    planted = Path(tempfile.mkdtemp(prefix="magpie-gw-test-", dir=account_cache)).resolve()
    try:
        (planted / "container_gateway").mkdir()
        done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(planted)}, home=lay.home)
        assert str(planted) not in done.stdout
        assert "refusing gateway source" in done.stderr
    finally:
        shutil.rmtree(planted, ignore_errors=True)


def test_a_home_nested_in_the_account_local_exempts_nothing_there(tmp_path: Path) -> None:
    """$HOME inside the account's ~/.local, with its own share/uv/python: that
    directory's exemption must not lift the account's ~/.local restriction."""
    import pwd
    import shutil
    import tempfile

    account_local = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".local"
    if not os.access(account_local, os.W_OK):
        pytest.skip("the account's ~/.local is not writable here")
    lay = Layout(tmp_path)
    fake_home = Path(tempfile.mkdtemp(prefix="magpie-gw-test-", dir=account_local)).resolve()
    try:
        planted = fake_home / ".local" / "share" / "uv" / "python" / "src"
        (planted / "container_gateway").mkdir(parents=True)
        done = run("start", lay.project, {"MAGPIE_CONTAINER_GATEWAY_SRC": str(planted)}, home=fake_home)
        assert str(planted) not in done.stdout
    finally:
        shutil.rmtree(fake_home, ignore_errors=True)


def _run_by_shebang(action: str, cwd: Path, env_extra: dict[str, str], home: Path) -> subprocess.CompletedProcess[str]:
    """As Claude Code runs it: the script itself, so its shebang applies."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_TMPDIR"}
    env.update({"MAGPIE_CONTAINER_GATEWAY_DRY_RUN": "1", "HOME": str(home), **env_extra})
    return subprocess.run([str(SCRIPT), action], input=json.dumps({"cwd": str(cwd)}),
                          capture_output=True, text=True, env=env, cwd=cwd, check=False)



@pytest.mark.parametrize("hostile", ["BASH_ENV", "BASH_FUNC_git%%", "BASH_FUNC_exec%%", "SHELLOPTS"])
def test_the_launch_environment_never_runs_code(tmp_path: Path, hostile: str) -> None:
    """Executed directly, as the hook is wired, the shebang's privileged mode keeps
    BASH_ENV, exported functions and SHELLOPTS from running anything."""
    lay = Layout(tmp_path)
    marker = lay.base / "launch-env-ran"
    rc = lay.base / "rc.sh"
    rc.write_text(f"touch {marker}\n")
    value = {
        "BASH_ENV": str(rc),
        "BASH_FUNC_git%%": f"() {{ touch {marker}; }}",
        "BASH_FUNC_exec%%": f"() {{ touch {marker}; }}",
        "SHELLOPTS": "xtrace",
    }[hostile]
    done = _run_by_shebang("start", lay.project, {hostile: value}, lay.home)
    assert done.returncode == 0, done.stderr
    assert not marker.exists()
    assert "+ " not in done.stderr  # no xtrace imported through SHELLOPTS
    assert f"container_gateway serve --project={lay.project}" in done.stdout


# --- linked worktrees: the main checkout is anchored on first use ---


def _linked_worktree(lay: Layout) -> Path:
    git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "-C", str(lay.project), "-c", "commit.gpgsign=false", "commit", "-q",
                    "--allow-empty", "-m", "init"], check=True, env=git_env)
    worktree = lay.base / "wt"
    subprocess.run(["git", "-C", str(lay.project), "worktree", "add", "-q", str(worktree)], check=True)
    return worktree


def _records(lay: Layout) -> list[Path]:
    state = lay.home / ".claude" / "magpie-gateway" / "worktrees"
    return sorted(p for p in state.iterdir() if not p.name.startswith(".")) if state.is_dir() else []


def test_the_first_run_records_the_worktree_main_checkout(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    worktree = _linked_worktree(lay)
    done = run("start", worktree, home=lay.home)
    assert f" -I -S {lay.src} " in done.stdout
    [record] = _records(lay)
    assert record.read_text().splitlines() == [str(worktree), str(lay.project)]


def test_a_changed_main_checkout_refuses_until_the_record_is_deleted(tmp_path: Path) -> None:
    """Rewritten .git metadata could otherwise hide the real main checkout's grants at session end."""
    lay = Layout(tmp_path)
    worktree = _linked_worktree(lay)
    run("start", worktree, home=lay.home)
    [record] = _records(lay)
    record.write_text(f"{worktree}\n{lay.base / 'the-real-main'}\n")
    done = run("stop", worktree, home=lay.home)
    assert done.stdout == ""
    assert "no longer matches its worktree record" in done.stderr and str(record) in done.stderr
    record.unlink()
    assert f" -I -S {lay.src} " in run("stop", worktree, home=lay.home).stdout


def test_a_symlinked_record_refuses(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    worktree = _linked_worktree(lay)
    run("start", worktree, home=lay.home)
    [record] = _records(lay)
    target = lay.base / "planted"
    target.write_text(record.read_text())
    record.unlink()
    record.symlink_to(target)
    done = run("start", worktree, home=lay.home)
    assert done.stdout == "" and "is a symlink" in done.stderr


def test_the_hook_uses_no_here_documents() -> None:
    """bash 3.2 backs <<< and << with temporary files; when one cannot be created
    the input is silently empty, and a check reading it would fail open."""
    text = SCRIPT.read_text()
    code = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    assert "<<" not in code


def test_turning_the_worktree_into_a_plain_checkout_refuses(tmp_path: Path) -> None:
    """Swapping the .git file for a directory must not make the record disappear."""
    lay = Layout(tmp_path)
    worktree = _linked_worktree(lay)
    run("start", worktree, home=lay.home)
    (worktree / ".git").unlink()
    (worktree / ".git").mkdir()
    done = run("stop", worktree, home=lay.home)
    assert done.stdout == "" and "no longer matches its worktree record" in done.stderr


def test_a_record_for_another_path_refuses(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    worktree = _linked_worktree(lay)
    run("start", worktree, home=lay.home)
    [record] = _records(lay)
    record.write_text(f"{lay.base / 'someone-else'}\n{lay.project}\n")
    done = run("start", worktree, home=lay.home)
    assert done.stdout == "" and "no longer matches its worktree record" in done.stderr


def test_a_record_in_a_writable_directory_is_never_trusted(tmp_path: Path) -> None:
    """A grant over the record directory lets the sandbox forge the record itself."""
    lay = Layout(tmp_path)
    worktree = _linked_worktree(lay)
    run("start", worktree, home=lay.home)
    lay.settings({"sandbox": {"filesystem": {"allowWrite": [str(lay.home / ".claude" / "magpie-gateway")]}}})
    done = run("stop", worktree, home=lay.home)
    assert done.stdout == "" and "is sandbox-writable" in done.stderr


def test_a_writable_record_directory_refuses_even_a_plain_checkout(tmp_path: Path) -> None:
    """Otherwise deleting the record and the .git file together would skip the check."""
    lay = Layout(tmp_path)
    lay.settings({"sandbox": {"filesystem": {"allowWrite": [str(lay.home / ".claude" / "magpie-gateway")]}}})
    done = run("start", lay.project, home=lay.home)
    assert done.stdout == "" and "is sandbox-writable" in done.stderr



def test_a_planted_core_worktree_cannot_move_the_record_key(tmp_path: Path) -> None:
    """A fake .git naming a parent as the toplevel still contains the cwd, but would
    key the worktree records differently and skip the existing one."""
    lay = Layout(tmp_path)
    worktree = _linked_worktree(lay)
    run("start", worktree, home=lay.home)
    # A plain .git directory (so the checkout no longer looks linked) whose config
    # names the parent as the work tree: git's toplevel then contains the cwd.
    (worktree / ".git").unlink()
    subprocess.run(["git", "init", "-q", str(worktree)], check=True)
    subprocess.run(["git", "-C", str(worktree), "config", "core.worktree", str(lay.base)], check=True)
    done = run("stop", worktree, home=lay.home)
    assert done.stdout == ""
    assert "but the checkout is" in done.stderr


def test_core_worktree_on_a_plain_checkout_refuses(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    subprocess.run(["git", "-C", str(lay.project), "config", "core.worktree", str(lay.project)], check=True)
    done = run("start", lay.project, home=lay.home)
    assert done.stdout == "" and "core.worktree is set" in done.stderr


def test_a_planted_bare_repository_is_not_discovered(tmp_path: Path) -> None:
    """In a project with no .git, HEAD / config / objects planted in the cwd would make
    git treat it as a bare repository whose core.worktree names a parent."""
    lay = Layout(tmp_path)
    plain = lay.base / "plain"
    plain.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", str(plain)], check=True)
    subprocess.run(["git", "--git-dir", str(plain), "config", "core.worktree", str(lay.base)], check=True)
    subprocess.run(["git", "--git-dir", str(plain), "config", "core.bare", "false"], check=True)
    done = run("start", plain, home=lay.home)
    # Either refused, or served for the directory itself: never for the parent.
    assert done.stdout == "" or f"--project={plain.resolve()} " in done.stdout
    assert f"--project={lay.base} " not in done.stdout


# --- ensure: waiting for the gateway it started ---

_FAKE_GATEWAY = '''
import json, os, sys, time
ctl = os.environ["FAKE_GW_DIR"]
mode = open(os.path.join(ctl, "mode")).read().strip()
cmd = sys.argv[1]
with open(os.path.join(ctl, "calls"), "a") as log:
    log.write(cmd + "\\n")
started = os.path.join(ctl, "started")
if cmd == "serve":
    if mode != "never":
        open(started, "w").write(str(time.time()))
    sys.exit(0)
if cmd == "status":
    if mode == "already":
        state = "serving"
    elif not os.path.exists(started):
        state = "down"
    else:
        age = time.time() - float(open(started).read())
        if mode == "dies":
            state = "starting" if age < 0.3 else "down"
        else:
            state = "starting" if age < 0.6 else "serving"
    print(json.dumps({"running": state != "down", "serving": ["docker"] if state == "serving" else []}))
    sys.exit(0 if state != "down" else 3)
'''


def _fake_gateway(lay: Layout, mode: str) -> Path:
    (lay.src / "container_gateway" / "__init__.py").write_text("")
    (lay.src / "container_gateway" / "__main__.py").write_text(_FAKE_GATEWAY)
    ctl = lay.base / "fake-gw"
    ctl.mkdir()
    (ctl / "mode").write_text(mode)
    return ctl


def _ensure_for_real(lay: Layout, ctl: Path) -> tuple[subprocess.CompletedProcess[str], float, list[str]]:
    env = {"CLAUDE_PROJECT_DIR": str(lay.project), "FAKE_GW_DIR": str(ctl)}
    began = time.monotonic()
    done = run("ensure", lay.project, env, home=lay.home, dry_run=False,
               payload=bash_payload(lay.project, "docker ps"))
    calls = (ctl / "calls").read_text().split() if (ctl / "calls").exists() else []
    return done, time.monotonic() - began, calls


def test_ensure_leaves_a_serving_gateway_alone(tmp_path: Path) -> None:
    lay = Layout(tmp_path)
    done, _, calls = _ensure_for_real(lay, _fake_gateway(lay, "already"))
    assert done.returncode == 0 and calls == ["status"]


def test_ensure_waits_until_the_gateway_serves(tmp_path: Path) -> None:
    """Holding the pid lock is not serving: the wait ends only once a backend socket is bound."""
    lay = Layout(tmp_path)
    ctl = _fake_gateway(lay, "slow")
    done, elapsed, calls = _ensure_for_real(lay, ctl)
    assert done.returncode == 0 and calls[:2] == ["status", "serve"]
    assert elapsed >= 0.6 and calls.count("status") >= 3


@pytest.mark.parametrize("mode", ["dies", "never"])
def test_ensure_stops_waiting_for_a_gateway_that_is_gone(tmp_path: Path, mode: str) -> None:
    """No backend (the gateway exits) or no start at all must not stall every container command for 5 s."""
    lay = Layout(tmp_path)
    done, elapsed, calls = _ensure_for_real(lay, _fake_gateway(lay, mode))
    assert done.returncode == 0 and "serve" in calls
    assert elapsed < 3


def test_a_settings_fifo_refuses_without_blocking(tmp_path: Path) -> None:
    """jq must never open a FIFO sandboxed code planted where a settings file would be."""
    lay = Layout(tmp_path)
    sub = lay.base / "other"
    (sub / ".claude").mkdir(parents=True)
    os.mkfifo(sub / ".claude" / "settings.json")
    done = ensure(lay, "docker ps", cwd=sub)
    assert done.stdout == "" and "not a readable regular file" in done.stderr
