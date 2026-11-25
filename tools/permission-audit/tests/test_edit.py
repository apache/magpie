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
import errno
import fcntl
import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from permission_audit import edit
from permission_audit.edit import apply_changes


def _write_settings(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_add_appends_new_entry_in_order(tmp_path):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": ["Bash(git status *)"]}})
    outcome = apply_changes(p, additions=["Bash(lychee *)"], removals=[])
    assert outcome.added == ["Bash(lychee *)"]
    assert outcome.removed == []
    final = json.loads(p.read_text())["permissions"]["allow"]
    assert final == ["Bash(git status *)", "Bash(lychee *)"]


def test_add_existing_entry_is_noop(tmp_path):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": ["Bash(lychee *)"]}})
    outcome = apply_changes(p, additions=["Bash(lychee *)"], removals=[])
    assert outcome.added == []
    final = json.loads(p.read_text())["permissions"]["allow"]
    assert final == ["Bash(lychee *)"]


def test_remove_drops_first_and_subsequent_duplicates(tmp_path):
    p = tmp_path / "settings.local.json"
    _write_settings(
        p,
        {"permissions": {"allow": ["Bash(uv run *)", "Bash(git status *)", "Bash(uv run *)"]}},
    )
    outcome = apply_changes(p, additions=[], removals=["Bash(uv run *)"])
    # Both duplicates removed.
    assert outcome.removed == ["Bash(uv run *)", "Bash(uv run *)"]
    final = json.loads(p.read_text())["permissions"]["allow"]
    assert final == ["Bash(git status *)"]


def test_remove_absent_entry_is_noop(tmp_path):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": ["Bash(git status *)"]}})
    outcome = apply_changes(p, additions=[], removals=["Bash(uv run *)"])
    assert outcome.removed == []
    assert outcome.added == []
    # File untouched.
    final = json.loads(p.read_text())["permissions"]["allow"]
    assert final == ["Bash(git status *)"]


def test_unrelated_keys_preserved(tmp_path):
    p = tmp_path / "settings.local.json"
    _write_settings(
        p,
        {
            "extraKnownMarketplaces": {"foo": "bar"},
            "permissions": {"allow": ["Bash(uv run *)"], "deny": ["Bash(rm -rf /)"]},
            "hooks": {"PostToolUse": [{"matcher": "X", "hooks": []}]},
        },
    )
    apply_changes(p, additions=["Bash(lychee *)"], removals=["Bash(uv run *)"])
    final = json.loads(p.read_text())
    assert final["extraKnownMarketplaces"] == {"foo": "bar"}
    assert final["permissions"]["deny"] == ["Bash(rm -rf /)"]
    assert final["hooks"] == {"PostToolUse": [{"matcher": "X", "hooks": []}]}
    assert final["permissions"]["allow"] == ["Bash(lychee *)"]


def test_missing_file_raises_unless_create(tmp_path):
    p = tmp_path / "absent.json"
    with pytest.raises(FileNotFoundError):
        apply_changes(p, additions=["x"], removals=[])
    outcome = apply_changes(p, additions=["x"], removals=[], create_if_missing=True)
    assert outcome.file_was_created is True
    assert outcome.added == ["x"]


def test_invalid_json_raises_value_error(tmp_path):
    p = tmp_path / "settings.local.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        apply_changes(p, additions=["x"], removals=[])


def test_non_object_top_level_raises(tmp_path):
    p = tmp_path / "settings.local.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="not an object"):
        apply_changes(p, additions=["x"], removals=[])


def test_allow_not_a_list_raises(tmp_path):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": "not-a-list"}})
    with pytest.raises(ValueError, match="not a list"):
        apply_changes(p, additions=["x"], removals=[])


def test_no_changes_does_not_rewrite_file(tmp_path):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": ["Bash(lychee *)"]}})
    mtime_before = p.stat().st_mtime_ns
    outcome = apply_changes(p, additions=["Bash(lychee *)"], removals=[])
    assert outcome.added == []
    assert outcome.removed == []
    # File should not have been rewritten — same mtime.
    assert p.stat().st_mtime_ns == mtime_before


def _before_first_lock(monkeypatch, competing_writer: Callable[[], object]) -> list[int]:
    """Run `competing_writer` once, after the edit has opened the file but
    before its exclusive lock is granted: the window in which another
    process can replace or remove the file. Returns the list of descriptors
    the edit asked to lock, one per attempt."""
    real_flock = fcntl.flock
    attempts: list[int] = []
    in_competitor = False

    def flock(fd, operation):
        nonlocal in_competitor
        if operation == fcntl.LOCK_EX and not in_competitor:
            attempts.append(fd)
            if len(attempts) == 1:
                in_competitor = True
                try:
                    competing_writer()
                finally:
                    in_competitor = False
        return real_flock(fd, operation)

    monkeypatch.setattr(fcntl, "flock", flock)
    return attempts


def test_writer_that_replaced_the_file_while_we_waited_is_not_lost(tmp_path, monkeypatch):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": []}})
    attempts = _before_first_lock(monkeypatch, lambda: apply_changes(p, additions=["A"], removals=[]))
    outcome = apply_changes(p, additions=["B"], removals=[])
    assert outcome.added == ["B"]
    assert json.loads(p.read_text())["permissions"]["allow"] == ["A", "B"]
    assert len(attempts) == 2  # the stale lock was dropped and retaken on the new file
    assert list(tmp_path.glob("*.tmp.*")) == []


def test_file_removed_while_we_waited_raises(tmp_path, monkeypatch):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": []}})
    _before_first_lock(monkeypatch, p.unlink)
    with pytest.raises(FileNotFoundError):
        apply_changes(p, additions=["A"], removals=[])
    assert not p.exists()


def test_file_removed_while_we_waited_is_recreated_when_allowed(tmp_path, monkeypatch):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": []}})
    attempts = _before_first_lock(monkeypatch, p.unlink)
    outcome = apply_changes(p, additions=["A"], removals=[], create_if_missing=True)
    assert outcome.file_was_created is True
    assert outcome.added == ["A"]
    assert json.loads(p.read_text()) == {"permissions": {"allow": ["A"]}}
    assert len(attempts) == 2


def test_gives_up_when_every_lock_lands_on_a_replaced_file(tmp_path, monkeypatch):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": []}})
    real_flock = fcntl.flock
    attempts = 0

    def replace_then_lock(fd, operation):
        nonlocal attempts
        if operation == fcntl.LOCK_EX:
            attempts += 1
            fresh = tmp_path / "fresh.json"
            _write_settings(fresh, {"permissions": {"allow": [f"X{attempts}"]}})
            os.replace(fresh, p)
        return real_flock(fd, operation)

    monkeypatch.setattr(fcntl, "flock", replace_then_lock)
    with pytest.raises(RuntimeError, match="replaced the file each time"):
        apply_changes(p, additions=["A"], removals=[])
    assert attempts == edit._LOCK_ATTEMPTS
    assert json.loads(p.read_text())["permissions"]["allow"] == [f"X{attempts}"]


def test_failure_after_lock_closes_the_file(tmp_path, monkeypatch):
    p = tmp_path / "settings.local.json"
    _write_settings(p, {"permissions": {"allow": []}})
    attempts = _before_first_lock(monkeypatch, lambda: None)

    def failing_check(fh, path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(edit, "_is_file_at", failing_check)
    with pytest.raises(PermissionError) as excinfo:
        apply_changes(p, additions=["A"], removals=[])
    monkeypatch.undo()
    # `excinfo` keeps the traceback, and with it the helper's frame, alive:
    # only an explicit close releases the descriptor (and its lock) here.
    assert excinfo.traceback
    with pytest.raises(OSError) as closed:
        os.fstat(attempts[0])
    assert closed.value.errno == errno.EBADF
    assert json.loads(p.read_text()) == {"permissions": {"allow": []}}
