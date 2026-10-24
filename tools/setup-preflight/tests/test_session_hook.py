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
