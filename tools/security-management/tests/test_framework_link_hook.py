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
"""The magpie-security-tools session hook: a writable framework copy per version."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "link-framework-path.sh"


def _plugin(tmp_path: Path, version: str) -> Path:
    root = tmp_path / f"plugin-{version}"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(f'{{\n  "version": "{version}"\n}}\n')
    (root / "tools" / "demo").mkdir(parents=True)
    (root / "tools" / "demo" / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    return root


def _run(home: Path, root: Path) -> None:
    env = {**os.environ, "HOME": str(home), "CLAUDE_PLUGIN_ROOT": str(root)}
    subprocess.run(["bash", str(HOOK)], env=env, input="", check=True, text=True)


def test_the_copy_is_writable_and_current_follows_upgrades(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    base = home / ".cache" / "apache-magpie" / "framework"
    _run(home, _plugin(tmp_path, "1.0"))
    project = base / "current" / "tools" / "demo"
    assert (project / "pyproject.toml").is_file()
    assert os.access(project, os.W_OK)  # uv run writes .venv and uv.lock here
    _run(home, _plugin(tmp_path, "2.0"))
    assert os.readlink(base / "current") == str(base / "2.0")


def test_a_real_directory_at_current_is_left_alone(tmp_path: Path) -> None:
    home = tmp_path / "home"
    current = home / ".cache" / "apache-magpie" / "framework" / "current"
    current.mkdir(parents=True)
    _run(home, _plugin(tmp_path, "1.0"))
    assert current.is_dir() and not current.is_symlink()


def test_concurrent_first_starts_publish_one_tree(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    root = _plugin(tmp_path, "1.0")
    env = {**os.environ, "HOME": str(home), "CLAUDE_PLUGIN_ROOT": str(root)}
    runs = [subprocess.Popen(["bash", str(HOOK)], env=env, stdin=subprocess.DEVNULL) for _ in range(4)]
    assert all(r.wait() == 0 for r in runs)
    base = home / ".cache" / "apache-magpie" / "framework"
    assert (base / "1.0" / ".complete").is_file()
    assert not list(base.glob(".staging.*")) or all(
        (p / ".complete").is_file() for p in base.glob(".staging.*")
    )
    assert not (base / ".lock.1.0").exists()


def test_a_lock_left_by_a_killed_installer_is_reclaimed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    base = home / ".cache" / "apache-magpie" / "framework"
    lock = base / ".lock.1.0"
    lock.mkdir(parents=True)
    dead = subprocess.run(
        ["bash", "-c", "echo $$"], capture_output=True, text=True, check=True
    ).stdout.strip()
    (lock / "pid").write_text(dead)
    _run(home, _plugin(tmp_path, "1.0"))
    assert (base / "1.0" / ".complete").is_file()
    assert not lock.exists()
