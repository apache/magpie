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

"""The plugin's session-start hook runs the plugin's own pre-flight, never the project's."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "plugins" / "magpie-setup"
HOOK = PLUGIN_ROOT / "hooks" / "check-upgrade.sh"


def run_hook(cwd: Path, data: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_DATA": str(data),
        "CLAUDE_PROJECT_DIR": str(cwd),
    }
    return subprocess.run(
        ["bash", str(HOOK)], input="{}", capture_output=True, text=True, env=env, cwd=cwd, check=False
    )


def test_a_package_in_the_project_does_not_shadow_the_plugin(project: Path, tmp_path: Path) -> None:
    """`python3 -m` would put the opened project, the hook's cwd, ahead of PYTHONPATH."""
    planted = project / "setup_preflight"
    planted.mkdir()
    marker = tmp_path / "planted-ran"
    code = f"open({str(marker)!r}, 'w').close()\nprint('PLANTED')\n"
    (planted / "__init__.py").write_text(code, encoding="utf-8")
    (planted / "isolated.py").write_text(code, encoding="utf-8")

    done = run_hook(project, tmp_path / "data")

    assert done.returncode == 0, done.stderr
    assert not marker.exists()
    assert "PLANTED" not in done.stdout
    assert "Apache Magpie plugin" in done.stdout


def test_a_python3_on_path_is_never_run(project: Path, tmp_path: Path) -> None:
    """The hook runs outside the sandbox; PATH comes from settings a project can set."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "path-python-ran"
    fake = bin_dir / "python3"
    fake.write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
    fake.chmod(0o755)
    env_path = f"{bin_dir}:{os.environ['PATH']}"
    done = subprocess.run(
        ["bash", str(HOOK)],
        input="{}",
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": env_path,
            "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
            "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
            "CLAUDE_PROJECT_DIR": str(project),
        },
        cwd=project,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert not marker.exists()
    assert "Apache Magpie plugin" in done.stdout


def test_pythonpath_does_not_reach_the_preflight(project: Path, tmp_path: Path) -> None:
    """-I drops PYTHONPATH: a planted setup_preflight there never runs."""
    planted = tmp_path / "pp" / "setup_preflight"
    planted.mkdir(parents=True)
    marker = tmp_path / "pp-ran"
    code = f"open({str(marker)!r}, 'w').close()\n"
    (planted / "__init__.py").write_text(code, encoding="utf-8")
    (planted / "isolated.py").write_text(code, encoding="utf-8")
    env = {
        **os.environ,
        "PYTHONPATH": str(tmp_path / "pp"),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
        "CLAUDE_PROJECT_DIR": str(project),
    }
    done = subprocess.run(
        ["bash", str(HOOK)], input="{}", capture_output=True, text=True, env=env, cwd=project, check=False
    )
    assert done.returncode == 0, done.stderr
    assert not marker.exists()


HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"


def _wired_command() -> str:
    import json

    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    return data["hooks"]["SessionStart"][0]["hooks"][0]["command"]


def test_the_hook_runs_a_fixed_bash_in_privileged_mode() -> None:
    """`bash` and `#!/usr/bin/env bash` both resolve through PATH, which a project can set."""
    assert _wired_command().startswith("/bin/bash -p ")
    assert HOOK.read_text(encoding="utf-8").splitlines()[0] == "#!/bin/bash -p"


def test_a_bash_on_path_is_never_run(project: Path, tmp_path: Path) -> None:
    """The wired command, run by a shell as Claude Code runs it, ignores a bash on PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "path-bash-ran"
    fake = bin_dir / "bash"
    fake.write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
    fake.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
        "CLAUDE_PROJECT_DIR": str(project),
    }
    done = subprocess.run(
        ["/bin/sh", "-c", _wired_command()],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        cwd=project,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert not marker.exists()
    assert "Apache Magpie plugin" in done.stdout


def test_bash_env_never_runs(project: Path, tmp_path: Path) -> None:
    """Executed directly, privileged mode keeps BASH_ENV and exported functions out."""
    marker = tmp_path / "bash-env-ran"
    rc = tmp_path / "rc.sh"
    rc.write_text(f"touch {marker}\n")
    env = {
        **os.environ,
        "BASH_ENV": str(rc),
        "BASH_FUNC_sed%%": f"() {{ touch {marker}; }}",
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
        "CLAUDE_PROJECT_DIR": str(project),
    }
    done = subprocess.run(
        [str(HOOK)], input="{}", capture_output=True, text=True, env=env, cwd=project, check=False
    )
    assert done.returncode == 0, done.stderr
    assert not marker.exists()
    assert "Apache Magpie plugin" in done.stdout


def test_a_skipped_preflight_still_reports_the_stale_uv_grant(project: Path, tmp_path: Path) -> None:
    """Without a trusted Python the ~/.local/share/uv cleanup cannot run; the hook
    must say the grant is still there rather than drop the warning silently."""
    import json

    if _chosen_python(project, tmp_path):
        pytest.skip("a trusted Python runs here, and the pre-flight removes the grant itself")
    if not any(Path(d, "jq").exists() for d in ("/usr/bin", "/bin")):
        pytest.skip("no system jq: the fallback can only say it could not check")
    home = tmp_path / "home"
    home.mkdir()
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.local.json").write_text(
        json.dumps({"sandbox": {"filesystem": {"allowWrite": ["~/.local/share/uv"]}}})
    )
    env = {
        **os.environ,
        "HOME": str(home),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
        "CLAUDE_PROJECT_DIR": str(project),
    }
    done = subprocess.run(
        [str(HOOK)],
        input=json.dumps({"cwd": str(project)}),
        capture_output=True,
        text=True,
        env=env,
        cwd=project,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("{"), f"no warning: {done.stdout!r}"
    message = json.loads(done.stdout)["systemMessage"]
    assert "~/.local/share/uv" in message
    assert str(project / ".claude" / "settings.local.json") in message
    # The file is reported, never edited without the pre-flight.
    assert "~/.local/share/uv" in (project / ".claude" / "settings.local.json").read_text()


def _skipped_preflight(project: Path, tmp_path: Path, extra: dict[str, object]) -> str:
    """Run the hook where no trusted Python exists (skipped elsewhere), with <extra> settings."""
    import json

    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (project / ".claude").mkdir(exist_ok=True)
    if _chosen_python(project, tmp_path):
        pytest.skip("a trusted Python runs here, and the pre-flight handles the grant itself")
    if not any(Path(d, "jq").exists() for d in ("/usr/bin", "/bin")):
        pytest.skip("no system jq: the fallback can only say it could not check")
    filesystem: dict[str, list[object]] = {}
    for key, value in extra.items():
        filesystem.setdefault(key, []).extend(value if isinstance(value, list) else [value])
    settings = {"sandbox": {"filesystem": filesystem}}
    (project / ".claude" / "settings.local.json").write_text(json.dumps(settings))
    env = {
        **os.environ,
        "HOME": str(home),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
        "CLAUDE_PROJECT_DIR": str(project),
    }
    return subprocess.run(
        [str(HOOK)],
        input=json.dumps({"cwd": str(project)}),
        capture_output=True,
        text=True,
        env=env,
        cwd=project,
        check=False,
    ).stdout


def test_a_read_grant_on_the_uv_dir_is_not_a_stale_write(project: Path, tmp_path: Path) -> None:
    """allowRead of ~/.local/share/uv is what the reference settings carry: no warning."""
    out = _skipped_preflight(project, tmp_path, {"allowRead": ["~/.local/share/uv/"]})
    assert "~/.local/share/uv" not in out


@pytest.mark.parametrize("grant", ["~", "~/.local", "~/.local/share/uv/python", "~/.local/./share//uv"])
def test_a_covering_or_nested_write_grant_is_reported(project: Path, tmp_path: Path, grant: str) -> None:
    import json

    out = _skipped_preflight(project, tmp_path, {"allowWrite": [grant]})
    message = json.loads(out)["systemMessage"]
    assert "~/.local/share/uv" in message
    assert str(project / ".claude" / "settings.local.json") in message


def _chosen_python(project: Path, tmp_path: Path) -> str:
    """The interpreter the hook picks, read from its own xtrace ("" for none)."""
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "trace-data"),
        "CLAUDE_PROJECT_DIR": str(project),
    }
    done = subprocess.run(
        ["/bin/bash", "-px", str(HOOK)],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        cwd=project,
        check=False,
    )
    chosen = [
        line.split("python=", 1)[1].strip("'") for line in done.stderr.splitlines() if "+ python=" in line
    ]
    return chosen[-1] if chosen else ""


def _root_owned_all_the_way(path: str) -> bool:
    """Every component of the real path (and the path as given) root-owned, no group/world write."""
    import stat

    def ok(p: str) -> bool:
        st = os.lstat(p)
        return st.st_uid == 0 and not st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)

    real = os.path.realpath(path)
    parts = Path(real).parts
    return all(ok(str(Path(*parts[: i + 1]))) for i in range(len(parts)))


def test_only_a_root_owned_interpreter_is_ever_run(project: Path, tmp_path: Path) -> None:
    """The sandbox runs as this user: a Python it can rewrite (Homebrew, a user-owned
    install) must never run outside it, whatever the settings grant."""
    chosen = _chosen_python(project, tmp_path)
    if chosen:
        assert _root_owned_all_the_way(chosen), chosen
        assert not chosen.startswith("/opt/homebrew/")
    homebrew = Path("/opt/homebrew/bin/python3")
    if homebrew.exists() and not _root_owned_all_the_way(str(homebrew)):
        assert not chosen.startswith(os.path.realpath(homebrew).rsplit("/bin/", 1)[0])


def test_settings_the_fallback_cannot_read_are_reported_as_unchecked(project: Path, tmp_path: Path) -> None:
    """A settings file that cannot be parsed leaves the grant unknown: say so, never guess."""
    import json

    if _chosen_python(project, tmp_path):
        pytest.skip("a trusted Python runs here, and the pre-flight reads the settings itself")
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (project / ".claude").mkdir(exist_ok=True)
    (project / ".claude" / "settings.local.json").write_text("{ not json")
    env = {
        **os.environ,
        "HOME": str(home),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
        "CLAUDE_PROJECT_DIR": str(project),
    }
    out = subprocess.run(
        [str(HOOK)],
        input=json.dumps({"cwd": str(project)}),
        capture_output=True,
        text=True,
        env=env,
        cwd=project,
        check=False,
    ).stdout
    message = json.loads(out)["systemMessage"]
    assert "could not check" in message
    assert str(project / ".claude" / "settings.local.json") in message


def test_a_relative_project_dir_outside_git_does_not_hang(tmp_path: Path) -> None:
    """CLAUDE_PROJECT_DIR comes from the environment and may be relative."""
    plain = tmp_path / "plain"
    plain.mkdir()
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
        "CLAUDE_PROJECT_DIR": ".",
    }
    done = subprocess.run(
        [str(HOOK)], input="{}", capture_output=True, text=True, env=env, cwd=plain, check=False, timeout=8
    )
    assert done.returncode == 0, done.stderr
    assert "Apache Magpie plugin" in done.stdout
