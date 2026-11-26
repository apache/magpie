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

"""Session-only ASF hosts for Antigravity (`agent-iso agy`), apache/magpie#2003.

Antigravity keeps its permission rules in one user-scope file, so the wrapper
passes an explicit ASF project's hosts with `agy --settings` for one session.
A fake `agy` prints its argv. The ASF check is the framework's own
`setup_preflight`, found next to the wrapper (this repository); a copy of the
wrapper in a bare directory, or in a tree with a changed selector, stands in
for a missing or tampered framework.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "agent-iso.sh"
BASH = shutil.which("bash") or "/bin/bash"
GIT = shutil.which("git") or "git"
REPO = Path(__file__).resolve().parents[3]
CHECKER = REPO / "plugins" / "magpie-setup" / "skills" / "setup"

ASF_HOSTS = [
    "lists.apache.org",
    "dist.apache.org",
    "repository.apache.org",
    "downloads.apache.org",
    "archive.apache.org",
    "cveprocess.apache.org",
]
USER_PERMISSIONS = {
    "allow": ["read_url(github.com)", "command(git status)"],
    "ask": ["command(git push)"],
    "deny": ["read_file(/home/u/.ssh)"],
}


def _fake_agy(bindir: Path) -> None:
    bindir.mkdir(parents=True, exist_ok=True)
    fake = bindir / "agy"
    fake.write_text('#!/bin/sh\nfor a in "$@"; do echo "ARG:$a"; done\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _checkout(tmp_path: Path, organization: str | None, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run([GIT, "init", "-q", str(repo)], check=True)
    if organization is not None:
        overrides = repo / ".apache-magpie-overrides"
        overrides.mkdir()
        (overrides / "project.md").write_text(f"# Project\n\norganization: {organization}\n")
    return repo


def _toplevel(path: Path) -> str:
    return subprocess.run(
        [GIT, "-C", str(path), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    ).stdout.strip()


def _ident(path: str) -> str:
    st = os.stat(path)
    born = getattr(st, "st_birthtime", None)
    return f"{st.st_dev}:{st.st_ino}" + ("" if born is None else f":{born!r}")


def _key(path: Path) -> str:
    """The approval key: the checkout's real path and the identity of it and its .git."""
    top = os.path.realpath(_toplevel(path))
    git_dir = os.path.join(top, ".git")
    return f"{top} {_ident(top)} {_ident(git_dir) if os.path.exists(git_dir) else '-'}"


def _home(tmp_path: Path, permissions: dict | None = USER_PERMISSIONS, raw: str | None = None) -> Path:
    home = tmp_path / "home"
    profile = home / ".gemini" / "antigravity-cli"
    profile.mkdir(parents=True)
    if raw is not None:
        (profile / "settings.json").write_text(raw)
    elif permissions is not None:
        (profile / "settings.json").write_text(json.dumps({"enableTerminalSandbox": True, "permissions": permissions}))
    return home


def _record(home: Path, line: str) -> Path:
    path = home / ".gemini" / "config" / "magpie-agy-asf"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(line + "\n")
    return path


def _run(
    tmp_path: Path,
    cwd: Path,
    home: Path,
    args: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
    record: str | None = "approve",
    script: Path | None = None,
) -> subprocess.CompletedProcess:
    """Launch `agent-iso agy`; `record` is the answer already given for this checkout, if any.

    By default the wrapper runs from a copy of this framework installed where agy
    stages its plugin, the only place it takes the ASF check from.
    """
    bindir = tmp_path / "bin"
    _fake_agy(bindir)
    if script is None:
        script = _plugin_install(home)
    if record is not None:
        top = subprocess.run([GIT, "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if top.returncode == 0:
            _record(home, f"{record} {_key(cwd)}")
    env = {
        "PATH": f"{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(home),
        "USER": "testuser",
        "SHELL": "/bin/sh",
        "TERM": "xterm",
        "LANG": "en_US.UTF-8",
        "TMPDIR": str(tmp_path),
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [BASH, str(script), "agent-iso", "agy", *(args or [])],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _args(result: subprocess.CompletedProcess) -> list[str]:
    return [line[4:] for line in result.stdout.splitlines() if line.startswith("ARG:")]


def _session_settings(result: subprocess.CompletedProcess) -> dict | None:
    args = _args(result)
    if "--settings" not in args:
        return None
    return json.loads(args[args.index("--settings") + 1])


def _plugin_install(home: Path, selector: str | None = "real", root: Path | None = None) -> Path:
    """A framework copy holding the wrapper and the ASF selector, by default where agy stages its plugin.

    `selector` is "real" for this repository's setup_preflight, None for none, or replacement module text.
    """
    if root is None:
        root = home / ".gemini" / "config" / "plugins" / "magpie"
    wrapper = root / "tools" / "agent-isolation" / "agent-iso.sh"
    if wrapper.exists():
        return wrapper
    wrapper.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, wrapper)
    pkg = root / "plugins" / "magpie-setup" / "skills" / "setup" / "setup_preflight"
    if selector == "real":
        shutil.copytree(CHECKER / "setup_preflight", pkg, ignore=shutil.ignore_patterns("__pycache__"))
    elif selector is not None:
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "organization_network.py").write_text(selector)
    return wrapper


def _framework_copy(tmp_path: Path, selector: str | None) -> Path:
    """A plugin install with no selector, or a replaced one."""
    return _plugin_install(tmp_path / "home", selector=selector)


@pytest.fixture(autouse=True)
def _checker_present() -> None:
    assert (CHECKER / "setup_preflight" / "organization_network.py").is_file()


def test_an_asf_project_gets_the_hosts_for_this_session_only(tmp_path: Path) -> None:
    repo = _checkout(tmp_path, "ASF")
    home = _home(tmp_path)
    before = (home / ".gemini" / "antigravity-cli" / "settings.json").read_text()

    result = _run(tmp_path, repo, home, ["-p", "hello"])

    assert result.returncode == 0, result.stderr
    settings = _session_settings(result)
    assert settings is not None
    allow = settings["permissions"]["allow"]
    assert [rule for rule in allow if rule.startswith("read_url(") and "apache.org" in rule] == [
        f"read_url({host})" for host in ASF_HOSTS
    ]
    assert _args(result)[-2:] == ["-p", "hello"]
    assert "for this session only" in result.stderr
    # Nothing is written to the user's profile.
    assert (home / ".gemini" / "antigravity-cli" / "settings.json").read_text() == before


def test_the_users_own_rules_are_carried_into_the_session(tmp_path: Path) -> None:
    # Whether agy merges or replaces the lists, the session keeps every user rule.
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path))

    permissions = _session_settings(result)["permissions"]
    assert permissions["allow"][:2] == USER_PERMISSIONS["allow"]
    assert permissions["ask"] == USER_PERMISSIONS["ask"]
    assert permissions["deny"] == USER_PERMISSIONS["deny"]


def test_relative_and_home_file_paths_are_made_absolute(tmp_path: Path) -> None:
    # agy refuses a relative file path in --settings, so it is anchored where agy runs.
    permissions = {
        "allow": ["read_file(*)", "command(git status)"],
        "ask": [],
        "deny": ["read_file(.env)", "write_file(.agents/hooks.json)", "read_file(~/.aws)", "read_file(/etc/x)"],
    }
    repo = _checkout(tmp_path, "ASF")
    home = _home(tmp_path, permissions)
    result = _run(tmp_path, repo, home)

    root = _toplevel(repo)
    lists = _session_settings(result)["permissions"]
    assert lists["deny"] == [
        f"read_file({root}/.env)",
        f"write_file({root}/.agents/hooks.json)",
        f"read_file({home}/.aws)",
        "read_file(/etc/x)",
    ]
    assert lists["allow"][:2] == ["read_file(*)", "command(git status)"]


def test_from_a_subdirectory_deny_paths_cover_it_and_the_root(tmp_path: Path) -> None:
    # agy's workspace is the launch directory: a relative deny must still bind there.
    permissions = {"allow": [], "ask": [], "deny": ["read_file(.env)"]}
    repo = _checkout(tmp_path, "ASF")
    sub = repo / "sub"
    sub.mkdir()
    result = _run(tmp_path, sub, _home(tmp_path, permissions))

    root = _toplevel(repo)
    deny = _session_settings(result)["permissions"]["deny"]
    assert f"read_file({root}/.env)" in deny
    assert any(rule.endswith("/sub/.env)") for rule in deny)


def test_an_already_listed_host_is_not_repeated(tmp_path: Path) -> None:
    permissions = {"allow": ["read_url(dist.apache.org)"], "ask": [], "deny": []}
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path, permissions))

    allow = _session_settings(result)["permissions"]["allow"]
    assert allow.count("read_url(dist.apache.org)") == 1


def test_no_user_profile_still_gets_only_the_asf_hosts(tmp_path: Path) -> None:
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path, None))

    permissions = _session_settings(result)["permissions"]
    assert permissions == {"allow": [f"read_url({host})" for host in ASF_HOSTS], "ask": [], "deny": []}


@pytest.mark.parametrize(
    "raw",
    [
        '{"permissions": {"deny": ["read_file(~/.ssh)"],}',  # trailing comma: not JSON
        '{"permissions": {"deny": "read_file(~/.ssh)"}}',  # not a list
        '{"permissions": ["x"]}',  # not an object
        '{"permissions": {"deny": [42]}}',  # not text
    ],
)
def test_an_unreadable_user_profile_means_no_grant(tmp_path: Path, raw: str) -> None:
    # Fail closed: passing empty lists could drop the user's deny rules.
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path, raw=raw))

    assert _session_settings(result) is None
    assert "starting without ASF hosts" in result.stderr


@pytest.mark.parametrize("organization", [None, "independent", "Apache"])
def test_a_project_not_declaring_asf_gets_nothing(tmp_path: Path, organization: str | None) -> None:
    result = _run(tmp_path, _checkout(tmp_path, organization), _home(tmp_path), ["-p", "hi"])

    assert result.returncode == 0, result.stderr
    assert _session_settings(result) is None
    assert _args(result) == ["-p", "hi"]


def test_outside_a_checkout_nothing_is_added(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    result = _run(tmp_path, plain, _home(tmp_path))

    assert _session_settings(result) is None


def test_git_environment_variables_cannot_pick_the_checkout(tmp_path: Path) -> None:
    # Launched outside any checkout, GIT_DIR / GIT_WORK_TREE naming an approved ASF one change nothing.
    asf = _checkout(tmp_path, "ASF")
    home = _home(tmp_path)
    _record(home, f"approve {_key(asf)}")
    plain = tmp_path / "plain"
    plain.mkdir()
    env = {"GIT_DIR": str(asf / ".git"), "GIT_WORK_TREE": str(asf)}
    result = _run(tmp_path, plain, home, extra_env=env, record=None)

    assert _session_settings(result) is None


@pytest.mark.parametrize("first", ["plugin", "mcp", "update", "--version", "--help", "-h"])
def test_non_session_commands_get_nothing(tmp_path: Path, first: str) -> None:
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), [first, "list"], record=None)

    assert _args(result) == [first, "list"]
    assert "approve" not in result.stderr


def test_without_an_answer_and_no_terminal_nothing_is_added(tmp_path: Path) -> None:
    # The first launch asks on the terminal; a headless one cannot, so it grants nothing.
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), ["-p", "hi"], record=None)

    assert _session_settings(result) is None
    assert _args(result) == ["-p", "hi"]
    assert "once in a terminal to approve" in result.stderr


def test_a_declined_checkout_gets_nothing(tmp_path: Path) -> None:
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), record="decline")

    assert _session_settings(result) is None


def test_an_approval_is_per_checkout(tmp_path: Path) -> None:
    home = _home(tmp_path)
    _record(home, "approve /somewhere/else 1:2")
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), home, record=None)

    assert _session_settings(result) is None


def test_a_new_repository_at_an_approved_path_is_asked_again(tmp_path: Path) -> None:
    repo = _checkout(tmp_path, "ASF")
    home = _home(tmp_path)
    old = _key(repo)
    _record(home, f"approve {old}")
    shutil.rmtree(repo)
    repo = _checkout(tmp_path, "ASF")
    # Hold the old inode so the new directory cannot reuse it.
    if _key(repo) == old:
        pytest.skip("the filesystem reused the directory's inode")

    result = _run(tmp_path, repo, home, record=None)
    assert _session_settings(result) is None


def test_the_force_switch_grants_without_an_answer(tmp_path: Path) -> None:
    result = _run(
        tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), extra_env={"AGENT_ISO_ASF": "1"}, record=None
    )

    assert _session_settings(result) is not None


def test_the_force_switch_does_not_reach_a_project_that_is_not_asf(tmp_path: Path) -> None:
    result = _run(tmp_path, _checkout(tmp_path, "independent"), _home(tmp_path), extra_env={"AGENT_ISO_ASF": "1"})

    assert _session_settings(result) is None


def test_the_opt_out_switch_adds_nothing(tmp_path: Path) -> None:
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), extra_env={"AGENT_ISO_ASF": "0"})

    assert _session_settings(result) is None


def test_the_users_own_settings_flag_is_left_alone(tmp_path: Path) -> None:
    own = '{"model":"x"}'
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), ["--settings", own])

    assert _args(result) == ["--settings", own]


def test_a_wrapper_without_its_framework_adds_nothing(tmp_path: Path) -> None:
    script = _framework_copy(tmp_path, selector=None)
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), script=script)

    assert _session_settings(result) is None


def test_a_selector_returning_other_hosts_is_refused(tmp_path: Path) -> None:
    # Only the reviewed host list counts, whatever the selector says.
    script = _framework_copy(
        tmp_path,
        selector='import json\nprint(json.dumps({"sandbox": {"network": {"allowedDomains": ["evil.example"]}}}))\n',
    )
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), script=script)

    assert _session_settings(result) is None
    assert "unexpected hosts" in result.stderr


def test_the_selector_runs_without_the_callers_credentials(tmp_path: Path) -> None:
    probe = tmp_path / "seen-env.json"
    script = _framework_copy(
        tmp_path,
        selector=(
            "import json, os\n"
            f"open({str(probe)!r}, 'w').write(json.dumps(dict(os.environ)))\n"
            "print('{}')\n"
        ),
    )
    _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), script=script, extra_env={"GH_TOKEN": "secret"})

    seen = json.loads(probe.read_text())
    assert "GH_TOKEN" not in seen
    assert set(seen) <= {"PATH", "HOME", "PYTHONPATH", "__CF_USER_TEXT_ENCODING", "LC_CTYPE", "PWD"}


def test_a_checker_planted_in_the_checkout_is_never_imported(tmp_path: Path) -> None:
    # A project that is not ASF ships its own setup_preflight claiming the hosts:
    # the wrapper imports only its own framework's copy, never the working tree's.
    repo = _checkout(tmp_path, "independent")
    planted = repo / "setup_preflight"
    planted.mkdir()
    (planted / "__init__.py").write_text("")
    hosts = json.dumps({"sandbox": {"network": {"allowedDomains": ASF_HOSTS}}})
    (planted / "organization_network.py").write_text(f"print({hosts!r})\n")

    assert _session_settings(_run(tmp_path, repo, _home(tmp_path))) is None


def test_without_the_agy_plugin_nothing_is_added(tmp_path: Path) -> None:
    # The check is taken only from agy's installed plugin, never from beside the wrapper.
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), script=SCRIPT)

    assert _session_settings(result) is None


def test_the_user_scope_wrapper_copy_uses_the_agy_plugins_check(tmp_path: Path) -> None:
    # The supported wrapper is a lone copy (~/.claude/agent-isolation/agent-iso.sh, #2387).
    home = _home(tmp_path)
    _plugin_install(home)
    lone = home / ".claude" / "agent-isolation" / "agent-iso.sh"
    lone.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, lone)
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), home, script=lone)

    assert _session_settings(result) is not None


def test_a_plugin_directory_symlinked_elsewhere_is_not_trusted(tmp_path: Path) -> None:
    # A symlink would take the check out of the directory the profile protects.
    home = _home(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    _plugin_install(elsewhere, root=elsewhere / "magpie")
    plugins = home / ".gemini" / "config" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "magpie").symlink_to(elsewhere / "magpie")
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), home, script=SCRIPT)

    assert _session_settings(result) is None


def test_a_symlink_inside_the_selector_package_is_not_trusted(tmp_path: Path) -> None:
    home = _home(tmp_path)
    _plugin_install(home)
    pkg = home / ".gemini" / "config" / "plugins" / "magpie" / "plugins" / "magpie-setup" / "skills" / "setup" / "setup_preflight"
    target = tmp_path / "outside.py"
    target.write_text("")
    (pkg / "planted.py").symlink_to(target)
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), home, script=SCRIPT)

    assert _session_settings(result) is None


def test_the_magpie_plugin_linked_to_another_plugin_is_not_trusted(tmp_path: Path) -> None:
    home = _home(tmp_path)
    plugins = home / ".gemini" / "config" / "plugins"
    _plugin_install(home, root=plugins / "other")
    (plugins / "magpie").symlink_to(plugins / "other")
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), home, script=SCRIPT)

    assert _session_settings(result) is None


def test_a_shell_that_replays_only_the_functions_still_grants(tmp_path: Path) -> None:
    # Claude Code's Bash tool replays sourced functions with `typeset -f`, dropping plain variables.
    home = _home(tmp_path)
    script = _plugin_install(home)
    repo = _checkout(tmp_path, "ASF")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "TERM": "xterm", "AGENT_ISO_ASF": "1"}
    dump = subprocess.run(
        [BASH, "-c", f"source {str(script)!r} >/dev/null; declare -f"],
        env=env, capture_output=True, text=True, timeout=30, check=True,
    ).stdout
    result = subprocess.run(
        [BASH, "-c", dump + "\nagent_iso_agy_asf_settings -p hi"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=30,
    )
    assert json.loads(result.stdout)["permissions"]["allow"][-1] == "read_url(cveprocess.apache.org)"


@pytest.mark.skipif(shutil.which("zsh") is None, reason="needs zsh")
def test_zsh_grants_too(tmp_path: Path) -> None:
    home = _home(tmp_path)
    script = _plugin_install(home)
    repo = _checkout(tmp_path, "ASF")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "TERM": "xterm", "AGENT_ISO_ASF": "1"}
    result = subprocess.run(
        [shutil.which("zsh"), "-f", "-c", f"setopt noclobber; source {str(script)!r}; agent_iso_agy_asf_settings -p hi"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=30,
    )
    assert json.loads(result.stdout)["permissions"]["allow"][-1] == "read_url(cveprocess.apache.org)", result.stderr


def test_only_the_agy_plugin_install_is_trusted(tmp_path: Path) -> None:
    home = _home(tmp_path)
    script = _plugin_install(home, root=home / ".claude" / "plugins" / "cache" / "magpie")
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), home, script=script)

    assert _session_settings(result) is None


def test_the_sandbox_switches_ride_along(tmp_path: Path) -> None:
    home = _home(tmp_path)
    profile = home / ".gemini" / "antigravity-cli" / "settings.json"
    profile.write_text(
        json.dumps(
            {
                "enableTerminalSandbox": True,
                "toolPermission": "proceed-in-sandbox",
                "allowNonWorkspaceAccess": False,
                "model": "not-copied",
                "permissions": USER_PERMISSIONS,
            }
        )
    )
    settings = _session_settings(_run(tmp_path, _checkout(tmp_path, "ASF"), home))

    assert settings["enableTerminalSandbox"] is True
    assert settings["toolPermission"] == "proceed-in-sandbox"
    assert settings["allowNonWorkspaceAccess"] is False
    assert "model" not in settings


@pytest.mark.parametrize("rule", ["read_file(*.pem)", "read_file(secrets/**)", "read_file(~bob/.ssh)"])
def test_a_rule_that_cannot_be_made_absolute_means_no_grant(tmp_path: Path, rule: str) -> None:
    permissions = {"allow": [], "ask": [], "deny": [rule]}
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path, permissions))

    assert _session_settings(result) is None
    assert "cannot be made absolute" in result.stderr


def test_core_worktree_cannot_borrow_an_approved_checkout(tmp_path: Path) -> None:
    asf = _checkout(tmp_path, "ASF", name="asf")
    home = _home(tmp_path)
    _record(home, f"approve {_key(asf)}")
    other = _checkout(tmp_path, None, name="other")
    subprocess.run([GIT, "-C", str(other), "config", "core.worktree", str(asf)], check=True)

    result = _run(tmp_path, other, home, record=None)
    assert _session_settings(result) is None


def test_git_config_variables_cannot_borrow_an_approved_checkout(tmp_path: Path) -> None:
    asf = _checkout(tmp_path, "ASF", name="asf")
    home = _home(tmp_path)
    _record(home, f"approve {_key(asf)}")
    other = _checkout(tmp_path, None, name="other")
    env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree", "GIT_CONFIG_VALUE_0": str(asf)}

    result = _run(tmp_path, other, home, extra_env=env, record=None)
    assert _session_settings(result) is None


def test_an_active_virtualenvs_startup_code_never_runs(tmp_path: Path) -> None:
    # A .pth in the site-packages of the python3 on PATH would run outside the sandbox.
    venv = tmp_path / "venv"
    subprocess.run([shutil.which("python3") or "python3", "-m", "venv", "--without-pip", str(venv)], check=True)
    marker = tmp_path / "pth-ran"
    site = next(venv.glob("lib/python*/site-packages"))
    (site / "evil.pth").write_text(f"import pathlib; pathlib.Path({str(marker)!r}).write_text('x')\n")
    env = {"PATH": f"{tmp_path / 'bin'}:{venv / 'bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}"}

    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), extra_env=env)
    assert _session_settings(result) is not None
    assert not marker.exists()


@pytest.mark.parametrize("where", ["checkout", "tmp"])
def test_a_python3_an_agent_could_have_planted_is_never_run(tmp_path: Path, where: str) -> None:
    # A python3 found first on PATH inside the checkout (an active .venv) or a temp directory is refused.
    repo = _checkout(tmp_path, "ASF")
    bindir = (repo / ".venv" / "bin") if where == "checkout" else (tmp_path / "planted")
    bindir.mkdir(parents=True)
    marker = tmp_path / "planted-ran"
    fake = bindir / "python3"
    fake.write_text(f"#!/bin/sh\ntouch {str(marker)!r}\n")
    fake.chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}"}

    result = _run(tmp_path, repo, _home(tmp_path), extra_env=env)
    assert _session_settings(result) is None
    assert not marker.exists()
    assert "python3 on PATH is inside" in result.stderr


def test_no_git_from_path_is_run(tmp_path: Path) -> None:
    # The checkout root is found by looking for .git, so a git first on PATH is never run.
    marker = tmp_path / "git-ran"
    bindir = tmp_path / "shadow"
    bindir.mkdir()
    fake = bindir / "git"
    fake.write_text(f'#!/bin/sh\ntouch {str(marker)!r}\nexec {GIT!r} "$@"\n')
    fake.chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}"}
    home = _home(tmp_path)
    script = _plugin_install(home)
    repo = _checkout(tmp_path, "ASF")
    _record(home, f"approve {_key(repo)}")
    # Call the grant function alone: agent_iso_run's older cwd_toplevel lookup still uses git.
    result = subprocess.run(
        [BASH, "-c", f'source {str(script)!r}; agent_iso_agy_asf_settings -p hi'],
        cwd=repo,
        env={**env, "HOME": str(home), "TERM": "xterm"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(result.stdout)["permissions"]["allow"][-1] == "read_url(cveprocess.apache.org)"
    assert not marker.exists()


def test_a_python3_in_a_directory_above_the_launch_directory_is_never_run(tmp_path: Path) -> None:
    # Launched from repo/sub, a python3 planted in repo/.venv/bin sits outside the launch directory.
    home = _home(tmp_path)
    repo = home / "code" / "repo"
    repo.mkdir(parents=True)
    subprocess.run([GIT, "init", "-q", str(repo)], check=True)
    (repo / ".apache-magpie-overrides").mkdir()
    (repo / ".apache-magpie-overrides" / "project.md").write_text("organization: ASF\n")
    sub = repo / "sub"
    sub.mkdir()
    bindir = repo / ".venv" / "bin"
    bindir.mkdir(parents=True)
    # It behaves like python3, so only the refusal keeps the grant away.
    fake = bindir / "python3"
    real_python = os.path.realpath(shutil.which("python3") or "/usr/bin/python3")
    fake.write_text(f'#!/bin/sh\nexec {real_python!r} "$@"\n')
    fake.chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}", "AGENT_ISO_ASF": "1"}

    result = _run(tmp_path, sub, home, extra_env=env, record=None)
    assert _session_settings(result) is None
    # Control: the same launch with the real python3 first on PATH grants.
    env["PATH"] = f"{tmp_path / 'bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}"
    assert _session_settings(_run(tmp_path, sub, home, extra_env=env, record=None)) is not None


def test_sourcing_the_wrapper_runs_no_python(tmp_path: Path) -> None:
    marker = tmp_path / "python-ran"
    bindir = tmp_path / "shadow"
    bindir.mkdir()
    fake = bindir / "python3"
    fake.write_text(f"#!/bin/sh\ntouch {str(marker)!r}\n")
    fake.chmod(0o755)
    home = _home(tmp_path)
    script = _plugin_install(home)
    subprocess.run(
        [BASH, "-c", f"source {str(script)!r}"],
        env={"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(home)},
        check=True,
        timeout=30,
    )
    assert not marker.exists()


def test_help_anywhere_in_the_arguments_gets_nothing(tmp_path: Path) -> None:
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), _home(tmp_path), ["--model", "x", "--help"])

    assert _args(result) == ["--model", "x", "--help"]


def test_a_trailing_slash_on_home_is_ignored(tmp_path: Path) -> None:
    permissions = {"allow": [], "ask": [], "deny": ["read_file(~/.ssh)"]}
    home = _home(tmp_path, permissions)
    script = _plugin_install(home)
    result = _run(tmp_path, _checkout(tmp_path, "ASF"), home, extra_env={"HOME": f"{home}/"}, script=script)

    assert _session_settings(result)["permissions"]["deny"] == [f"read_file({home}/.ssh)"]


def test_a_symlinked_launch_directory_is_covered_by_its_real_path_too(tmp_path: Path) -> None:
    permissions = {"allow": [], "ask": [], "deny": ["read_file(.env)"]}
    repo = _checkout(tmp_path, "ASF")
    link = tmp_path / "link"
    link.symlink_to(repo)
    home = _home(tmp_path, permissions)
    script = _plugin_install(home)
    bindir = tmp_path / "bin"
    _fake_agy(bindir)
    _record(home, f"approve {_key(repo)}")
    env = {
        "PATH": f"{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(home),
        "TERM": "xterm",
        "PWD": str(link),
    }
    # `cd` through the symlink so $PWD stays logical.
    result = subprocess.run(
        [BASH, "-c", f'cd {str(link)!r} && exec bash {str(script)!r} agent-iso agy'],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    deny = _session_settings(result)["permissions"]["deny"]
    assert f"read_file({link}/.env)" in deny
    assert f"read_file({os.path.realpath(repo)}/.env)" in deny


def test_other_harnesses_get_no_antigravity_settings(tmp_path: Path) -> None:
    repo = _checkout(tmp_path, "ASF")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "codex"
    fake.write_text('#!/bin/sh\nfor a in "$@"; do echo "ARG:$a"; done\n')
    fake.chmod(0o755)
    env = {
        "PATH": f"{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(_home(tmp_path)),
        "TERM": "xterm",
        "AGENT_ISO_ASF": "1",
    }
    result = subprocess.run(
        [BASH, str(SCRIPT), "agent-iso", "codex", "x"], cwd=repo, env=env, capture_output=True, text=True, timeout=30
    )
    assert [line for line in result.stdout.splitlines() if line.startswith("ARG:")] == ["ARG:x"]
