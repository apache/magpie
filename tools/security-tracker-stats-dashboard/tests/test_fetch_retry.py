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

"""Guards the retry behaviour and the cache default of the issue-list fetch.

`fetch_issues.py` used to run `gh` exactly once and turn any non-zero exit into a
`SystemExit`. A single transient `HTTP 502` from the API therefore aborted the
entire dashboard run, and because this fetch is the first of six steps the
operator had to restart the pipeline by hand. `run_gh` (`gh_retry.py`, shared with
`fetch_roster.py`) now retries the failures
that can clear on their own, while still failing fast on the ones that cannot:
an auth error or a bad repo slug never fixes itself, and retrying it only delays
the error the operator needs to see.

The default cache location is guarded here too. It sits under the platform temp
root rather than a hardcoded `/tmp`, because a sandboxed run is granted its own
scratch directory and cannot write `/tmp` at all.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import types

import pytest

TOOL_DIR = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str):
    """Load a script from the tool directory as a module; importing it has no side effects."""
    if str(TOOL_DIR) not in sys.path:
        sys.path.insert(0, str(TOOL_DIR))
    spec = importlib.util.spec_from_file_location(name, TOOL_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_fetch_issues():
    return _load("fetch_issues")


def _load_gh_retry():
    return _load("gh_retry")


def _result(returncode: int, stderr: str = "", stdout: str = "") -> types.SimpleNamespace:
    """Stand-in for `subprocess.CompletedProcess`, which is all `run_gh` reads."""
    return types.SimpleNamespace(returncode=returncode, stderr=stderr, stdout=stdout)


def _patch_gh(monkeypatch, module, responses: list):
    """Replace `gh` and `sleep`, returning the recorded calls and delays."""
    calls: list[list[str]] = []
    sleeps: list[float] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        response = responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", fake_sleep)
    return calls, sleeps


def test_transient_failures_are_recognised():
    """The statuses `gh` surfaces for a server-side hiccup are all retryable."""
    fi = _load_gh_retry()
    assert fi.is_transient_failure("HTTP 502: Bad Gateway (https://api.github.com/graphql)")
    assert fi.is_transient_failure("HTTP 503: Service Unavailable")
    assert fi.is_transient_failure("HTTP 504: Gateway Time-out")
    assert fi.is_transient_failure("error: request timed out")


def test_non_transient_failures_are_not_retried():
    """Auth errors, a bad repo slug, and a missing CLI never clear on their own."""
    fi = _load_gh_retry()
    assert not fi.is_transient_failure("gh: Not Found (HTTP 404)")
    assert not fi.is_transient_failure("gh: Bad credentials (HTTP 401)")
    assert not fi.is_transient_failure("unknown flag: --state")
    assert not fi.is_transient_failure("")


def test_retries_transient_failure_then_succeeds(monkeypatch):
    """One 502 no longer aborts the run, and the backoff doubles between attempts."""
    fi = _load_gh_retry()
    calls, sleeps = _patch_gh(
        monkeypatch,
        fi,
        [
            _result(1, stderr="HTTP 502: Bad Gateway"),
            _result(1, stderr="HTTP 502: Bad Gateway"),
            _result(0, stdout="[]"),
        ],
    )

    assert fi.run_gh(["gh", "issue", "list"]).returncode == 0
    assert len(calls) == 3
    assert sleeps == [2.0, 4.0]


def test_gives_up_after_the_attempt_limit(monkeypatch):
    """A sustained outage still fails, so the operator learns the fetch is dead."""
    fi = _load_gh_retry()
    calls, sleeps = _patch_gh(
        monkeypatch,
        fi,
        [_result(1, stderr="HTTP 503: Service Unavailable") for _ in range(fi.ATTEMPTS)],
    )

    with pytest.raises(SystemExit) as exc:
        fi.run_gh(["gh", "issue", "list"])
    assert "503" in str(exc.value)
    assert len(calls) == fi.ATTEMPTS
    assert len(sleeps) == fi.ATTEMPTS - 1


def test_non_transient_failure_raises_on_the_first_attempt(monkeypatch):
    """No backoff is spent on an error that a retry cannot change."""
    fi = _load_gh_retry()
    calls, sleeps = _patch_gh(monkeypatch, fi, [_result(1, stderr="gh: Bad credentials (HTTP 401)")])

    with pytest.raises(SystemExit):
        fi.run_gh(["gh", "issue", "list"])
    assert len(calls) == 1
    assert sleeps == []


def test_default_cache_root_is_under_the_temp_root(monkeypatch):
    """The unset default has to be a directory a sandboxed run can actually write."""
    monkeypatch.delenv("TRACKER_STATS_CACHE", raising=False)
    fi = _load_fetch_issues()
    assert pathlib.Path(fi.ROOT) == pathlib.Path(tempfile.gettempdir()) / "tracker-stats-cache"


def test_cache_root_honours_the_env_override(monkeypatch, tmp_path):
    """An explicit TRACKER_STATS_CACHE still wins, so adopters keep control."""
    monkeypatch.setenv("TRACKER_STATS_CACHE", str(tmp_path))
    fi = _load_fetch_issues()
    assert pathlib.Path(fi.ROOT) == tmp_path


def test_timeout_is_retried_like_a_transient_failure(monkeypatch):
    """A call that hangs past its timeout is retried instead of aborting the run."""
    fi = _load_gh_retry()
    calls, sleeps = _patch_gh(
        monkeypatch,
        fi,
        [subprocess.TimeoutExpired(["gh"], 300), _result(0, stdout="[]")],
    )

    assert fi.run_gh(["gh", "issue", "list"]).returncode == 0
    assert len(calls) == 2
    assert sleeps == [2.0]


def test_timeout_on_every_attempt_fails(monkeypatch):
    """A fetch that never answers still ends in a clear failure."""
    fi = _load_gh_retry()
    _patch_gh(monkeypatch, fi, [subprocess.TimeoutExpired(["gh"], 300) for _ in range(fi.ATTEMPTS)])

    with pytest.raises(SystemExit, match="timed out"):
        fi.run_gh(["gh", "issue", "list"])


def test_roster_fetch_uses_the_retrying_helper():
    """fetch_roster.py goes through run_gh, so one 502 there no longer aborts the run."""
    source = (TOOL_DIR / "fetch_roster.py").read_text(encoding="utf-8")
    assert "from gh_retry import run_gh" in source
    assert "subprocess.run(" not in source
