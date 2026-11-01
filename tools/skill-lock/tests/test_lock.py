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

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from skill_lock import (
    EXIT_ALREADY_RUNNING,
    EXIT_ERROR,
    EXIT_OK,
    _take_over,
    acquire,
    list_locks,
    lock_path,
    main,
    read_owner,
    release,
    renew,
    scope_name,
    status,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def adopted(tmp_path: Path) -> Path:
    """An adopted project: the lock lives under .apache-magpie-local/run/locks."""
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    (root / ".apache-magpie.lock").write_text("method: local\n")
    return root


def test_scope_name_is_one_safe_path_component() -> None:
    assert scope_name("issue-triage", "apache/example") == "issue-triage@apache__example"
    assert "/" not in scope_name("x", "a/b/c")
    with pytest.raises(ValueError):
        scope_name("", "apache/example")


def test_lock_lives_in_the_personal_layer_never_the_tree(adopted: Path) -> None:
    path = lock_path(adopted, "issue-triage", "apache/example")
    assert path == adopted / ".apache-magpie-local" / "run" / "locks" / "issue-triage@apache__example.lock"


def test_acquire_then_contend_then_release(adopted: Path) -> None:
    first = acquire(adopted, "issue-triage", "apache/example", now=NOW)
    assert first["status"] == "acquired"
    assert first["token"]
    assert lock_path(adopted, "issue-triage", "apache/example").is_dir()

    second = acquire(adopted, "issue-triage", "apache/example", now=NOW + timedelta(minutes=5))
    assert second["status"] == "already_running"
    assert second["holder"]["token"] == first["token"]
    assert "--force" in second["hint"]

    assert status(adopted, "issue-triage", "apache/example", now=NOW)["status"] == "held"
    out = release(adopted, "issue-triage", "apache/example", token=first["token"])
    assert out["status"] == "released" and out["was_held"] is True
    assert status(adopted, "issue-triage", "apache/example")["status"] == "free"


def test_scopes_do_not_contend(adopted: Path) -> None:
    assert acquire(adopted, "issue-triage", "apache/a", now=NOW)["status"] == "acquired"
    assert acquire(adopted, "issue-triage", "apache/b", now=NOW)["status"] == "acquired"
    assert acquire(adopted, "issue-stale-sweep", "apache/a", now=NOW)["status"] == "acquired"
    assert len(list_locks(adopted, now=NOW)["locks"]) == 3


def test_expired_lease_is_stale_and_taken_over(adopted: Path) -> None:
    acquire(adopted, "issue-triage", "apache/example", ttl=60, now=NOW)
    later = NOW + timedelta(seconds=61)
    assert status(adopted, "issue-triage", "apache/example", now=later)["status"] == "stale"
    taken = acquire(adopted, "issue-triage", "apache/example", now=later)
    assert taken["status"] == "acquired"
    assert "lease expired" in taken["took_over_stale"]


def test_dead_owner_pid_on_this_host_is_stale(adopted: Path) -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    dead_pid = proc.pid  # exited and reaped; pid reuse within one test is vanishingly unlikely
    acquire(adopted, "issue-triage", "apache/example", owner_pid=dead_pid, now=NOW)
    taken = acquire(adopted, "issue-triage", "apache/example", now=NOW + timedelta(seconds=1))
    assert taken["status"] == "acquired"
    assert "pid" in taken["took_over_stale"]


def test_two_takeovers_of_one_stale_lock_cannot_both_acquire(adopted: Path) -> None:
    # Runs A and B both read the same expired owner. A takes over and holds a
    # fresh lock; B's takeover from its earlier read must lose and leave A's
    # live lock in place.
    acquire(adopted, "issue-triage", "apache/example", ttl=60, now=NOW)
    lock = lock_path(adopted, "issue-triage", "apache/example")
    stale = read_owner(lock)
    later = NOW + timedelta(seconds=61)
    a = acquire(adopted, "issue-triage", "apache/example", now=later)
    assert a["status"] == "acquired"
    assert _take_over(lock, stale) is False
    holder = read_owner(lock)
    assert holder is not None and holder["token"] == a["token"]
    assert not list(lock.parent.glob(f"{lock.name}.stale-*")), "no tombstone may be left behind"


def test_live_owner_pid_is_respected(adopted: Path) -> None:
    acquire(adopted, "issue-triage", "apache/example", owner_pid=os.getpid(), now=NOW)
    assert acquire(adopted, "issue-triage", "apache/example", now=NOW)["status"] == "already_running"


def test_lock_without_owner_file_is_respected_not_stolen(adopted: Path) -> None:
    lock = lock_path(adopted, "issue-triage", "apache/example")
    lock.mkdir(parents=True)  # a racing starter between mkdir and its write
    out = acquire(adopted, "issue-triage", "apache/example", now=NOW)
    assert out["status"] == "already_running"
    assert out["holder"] is None
    assert lock.is_dir()


def test_release_with_wrong_token_refuses_unless_forced(adopted: Path) -> None:
    acquire(adopted, "issue-triage", "apache/example", now=NOW)
    out = release(adopted, "issue-triage", "apache/example", token="not-it")
    assert out["status"] == "error"
    assert status(adopted, "issue-triage", "apache/example", now=NOW)["status"] == "held"
    out = release(adopted, "issue-triage", "apache/example", token="not-it", force=True)
    assert out["status"] == "released"


def test_lock_path_that_is_a_file_is_an_error_not_a_holder(adopted: Path) -> None:
    lock = lock_path(adopted, "issue-triage", "apache/example")
    lock.parent.mkdir(parents=True)
    lock.write_text("not a lock dir")
    out = acquire(adopted, "issue-triage", "apache/example", now=NOW)
    assert out["status"] == "error"
    assert "not a directory" in out["error"]


def test_release_of_a_free_lock_is_a_noop(adopted: Path) -> None:
    out = release(adopted, "issue-triage", "apache/example")
    assert out["status"] == "released" and out["was_held"] is False


def test_renew_extends_the_lease(adopted: Path) -> None:
    acquire(adopted, "issue-triage", "apache/example", ttl=60, now=NOW)
    renewed = renew(adopted, "issue-triage", "apache/example", ttl=3600, now=NOW + timedelta(seconds=50))
    assert renewed["status"] == "renewed"
    assert (
        status(adopted, "issue-triage", "apache/example", now=NOW + timedelta(seconds=120))["status"]
        == "held"
    )
    assert renew(adopted, "issue-triage", "apache/other")["status"] == "error"


def test_renew_with_a_token_refuses_another_holder(adopted: Path) -> None:
    first = acquire(adopted, "issue-triage", "apache/example", ttl=60, now=NOW)
    later = NOW + timedelta(seconds=61)
    second = acquire(adopted, "issue-triage", "apache/example", ttl=60, now=later)
    assert second["status"] == "acquired"
    refused = renew(adopted, "issue-triage", "apache/example", ttl=3600, token=first["token"], now=later)
    assert refused["status"] == "error"
    assert refused["holder"]["token"] == second["token"]
    lock = lock_path(adopted, "issue-triage", "apache/example")
    holder = read_owner(lock)
    assert holder is not None and holder["expires"] == second["expires"], (
        "the new holder's lease must be untouched"
    )
    ok = renew(adopted, "issue-triage", "apache/example", ttl=3600, token=second["token"], now=later)
    assert ok["status"] == "renewed"


def test_cli_exit_codes_and_json(adopted: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(
        ["--root", str(adopted), "acquire", "issue-triage", "--repo", "apache/example", "--note", "sweep"]
    )
    assert rc == EXIT_OK
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "acquired"

    rc = main(["--root", str(adopted), "acquire", "issue-triage", "--repo", "apache/example"])
    assert rc == EXIT_ALREADY_RUNNING
    second = json.loads(capsys.readouterr().out)
    assert second["status"] == "already_running"
    assert second["holder"]["note"] == "sweep"

    rc = main(
        ["--root", str(adopted), "release", "issue-triage", "--repo", "apache/example", "--token", "bad"]
    )
    assert rc == EXIT_ERROR
    capsys.readouterr()

    rc = main(
        [
            "--root",
            str(adopted),
            "release",
            "issue-triage",
            "--repo",
            "apache/example",
            "--token",
            first["token"],
        ]
    )
    assert rc == EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "released"

    rc = main(["--root", str(adopted), "status", "issue-triage", "--repo", "apache/example"])
    assert rc == EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "free"

    rc = main(["--root", str(adopted), "list"])
    assert rc == EXIT_OK
    assert json.loads(capsys.readouterr().out)["locks"] == []


def test_unadopted_repo_locks_in_the_git_directory(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    (root / ".git").mkdir(parents=True)
    path = lock_path(root, "issue-triage", "apache/example")
    assert path.is_relative_to(root / ".git" / "apache-magpie")
    assert acquire(root, "issue-triage", "apache/example", now=NOW)["status"] == "acquired"
