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
"""The magpie-vetted-ops session hook: the stable links, and the copy `vetted-op-checks` runs from."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "link-stable-path.sh"


def _plugin(tmp_path: Path, version: str) -> Path:
    """A read-only plugin root carrying tools/vetted-ops, as the plugin cache does."""
    root = tmp_path / f"plugin-{version}"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(f'{{\n  "version": "{version}"\n}}\n')
    (root / "tools" / "vetted-ops").mkdir(parents=True)
    (root / "tools" / "vetted-ops" / "pyproject.toml").write_text('[project]\nname = "vetted-ops"\n')
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    return root


def _run(home: Path, root: Path) -> None:
    env = {**os.environ, "HOME": str(home), "CLAUDE_PLUGIN_ROOT": str(root)}
    subprocess.run(["bash", str(HOOK)], env=env, input="", check=True, text=True)


def test_the_stable_link_still_points_into_the_plugin(tmp_path: Path) -> None:
    """Every command that runs outside the sandbox keeps the path the agent cannot edit."""
    home = tmp_path / "home"
    home.mkdir()
    root = _plugin(tmp_path, "1.0")
    _run(home, root)
    assert os.readlink(home / ".claude" / "magpie" / "vetted-ops") == str(root / "tools" / "vetted-ops")


def test_a_readable_copy_for_the_checks_follows_upgrades(tmp_path: Path) -> None:
    """`vetted-op-checks` runs sandboxed, where only ~/.cache is readable."""
    home = tmp_path / "home"
    home.mkdir()
    base = home / ".cache" / "apache-magpie" / "vetted-ops"
    _run(home, _plugin(tmp_path, "1.0"))
    assert (base / "current" / "pyproject.toml").is_file()
    assert os.access(base / "current", os.W_OK)  # uvx builds from it
    _run(home, _plugin(tmp_path, "2.0"))
    assert os.readlink(base / "current") == str(base / "2.0")
    assert (base / "2.0" / ".complete").is_file()


def test_a_real_directory_at_current_is_left_alone(tmp_path: Path) -> None:
    home = tmp_path / "home"
    current = home / ".cache" / "apache-magpie" / "vetted-ops" / "current"
    current.mkdir(parents=True)
    _run(home, _plugin(tmp_path, "1.0"))
    assert current.is_dir() and not current.is_symlink()


def test_a_plugin_without_the_package_copies_nothing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "plugin-bare"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text('{\n  "version": "1.0"\n}\n')
    _run(home, root)
    assert not (home / ".cache" / "apache-magpie" / "vetted-ops").exists()


def test_a_symlinked_cache_directory_is_never_followed(tmp_path: Path) -> None:
    """The hook runs outside the sandbox in a tree the sandbox can write."""
    home = tmp_path / "home"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (home / ".cache" / "apache-magpie").mkdir(parents=True)
    (home / ".cache" / "apache-magpie" / "vetted-ops").symlink_to(elsewhere)
    _run(home, _plugin(tmp_path, "1.0"))
    assert list(elsewhere.iterdir()) == []


def test_a_planted_symlink_at_the_version_is_left_alone(tmp_path: Path) -> None:
    home = tmp_path / "home"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    base = home / ".cache" / "apache-magpie" / "vetted-ops"
    base.mkdir(parents=True)
    (base / "1.0").symlink_to(elsewhere)
    _run(home, _plugin(tmp_path, "1.0"))
    assert list(elsewhere.iterdir()) == []
    assert not (base / "current").exists()


def test_a_lock_left_without_a_pid_is_reclaimed(tmp_path: Path) -> None:
    """An installer killed between taking the lock and writing its pid must not block the version for good."""
    home = tmp_path / "home"
    base = home / ".cache" / "apache-magpie" / "vetted-ops"
    lock = base / ".lock.1.0"
    lock.mkdir(parents=True)
    old = lock.stat().st_mtime - 120
    os.utime(lock, (old, old))
    _run(home, _plugin(tmp_path, "1.0"))
    assert (base / "current" / "pyproject.toml").is_file()
    assert not lock.exists()


def test_a_symlinked_staging_directory_is_never_followed(tmp_path: Path) -> None:
    """The copy is staged where the sandbox cannot write; a link planted there is refused, not followed."""
    home = tmp_path / "home"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (home / ".local" / "state").mkdir(parents=True)
    (home / ".local" / "state" / "apache-magpie").symlink_to(elsewhere)
    _run(home, _plugin(tmp_path, "1.0"))
    assert list(elsewhere.iterdir()) == []
    assert not (home / ".cache" / "apache-magpie" / "vetted-ops" / "current").exists()


def test_no_staging_directory_is_left_behind(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _run(home, _plugin(tmp_path, "1.0"))
    assert list((home / ".local" / "state" / "apache-magpie").iterdir()) == []


def test_a_link_into_a_checkout_is_left_alone(tmp_path: Path) -> None:
    """A framework checkout links the stable path into its own tools/; the plugin must not undo it."""
    home = tmp_path / "home"
    checkout = tmp_path / "code" / "magpie" / "tools" / "vetted-ops"
    checkout.mkdir(parents=True)
    magpie = home / ".claude" / "magpie"
    magpie.mkdir(parents=True)
    (magpie / "vetted-ops").symlink_to(checkout)
    _run(home, _plugin(tmp_path / "cache", "1.0"))
    assert os.readlink(magpie / "vetted-ops") == str(checkout)


def test_a_snapshot_copy_is_left_alone(tmp_path: Path) -> None:
    home = tmp_path / "home"
    copy = home / ".claude" / "magpie" / "vetted-ops"
    copy.mkdir(parents=True)
    (copy / "pyproject.toml").write_text("snapshot\n")
    _run(home, _plugin(tmp_path, "1.0"))
    assert not copy.is_symlink() and (copy / "pyproject.toml").read_text() == "snapshot\n"


def test_a_link_to_an_older_plugin_version_is_moved(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    old = _plugin(tmp_path / "cache", "1.0")
    _run(home, old)
    new = _plugin(tmp_path / "cache", "2.0")
    _run(home, new)
    assert os.readlink(home / ".claude" / "magpie" / "vetted-ops") == str(new / "tools" / "vetted-ops")
