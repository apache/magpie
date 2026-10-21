#!/usr/bin/env python3

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

"""Dump all tracker issues (state=all, no PRs) to <cache>/issues.json."""

import json
import os
import re
import subprocess
import sys
import tempfile
import time

# The cache defaults under the platform temp root rather than a hardcoded `/tmp`:
# a sandboxed run is typically granted its own scratch directory and cannot write
# `/tmp`, so `/tmp/tracker-stats-cache` made the first fetch step fail outright.
# `tempfile.gettempdir()` honours `$TMPDIR` (POSIX) and `%TEMP%` (Windows).
ROOT = os.environ.get("TRACKER_STATS_CACHE") or os.path.join(tempfile.gettempdir(), "tracker-stats-cache")
REPO = os.environ.get("TRACKER_STATS_REPO", "airflow-s/airflow-s")

# `gh` reports a server-side hiccup as a non-zero exit with the status in stderr.
# A single transient `HTTP 502` on the first call used to abort the entire
# dashboard run, so retry the failures that are worth retrying and fail fast on
# everything else (auth errors, a bad repo slug, an unknown flag).
_TRANSIENT_FAILURE = re.compile(
    r"HTTP\s+5\d\d"
    r"|Bad Gateway"
    r"|Service Unavailable"
    r"|Gateway Time-?out"
    r"|Internal Server Error"
    r"|connection reset"
    r"|timed out",
    re.IGNORECASE,
)

ATTEMPTS = 3
BASE_DELAY_SECONDS = 2.0


def is_transient_failure(stderr: str) -> bool:
    """True when a failed `gh` call looks like a retryable server-side error."""
    return bool(_TRANSIENT_FAILURE.search(stderr or ""))


def run_gh(
    args: list[str],
    *,
    attempts: int = ATTEMPTS,
    base_delay: float = BASE_DELAY_SECONDS,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """Run `gh`, retrying transient failures with exponential backoff.

    Raises `SystemExit` with the last stderr once the attempts are exhausted, or
    immediately for a failure that retrying cannot fix.
    """
    for attempt in range(1, attempts + 1):
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return r
        if attempt == attempts or not is_transient_failure(r.stderr):
            raise SystemExit(f"gh failed: {r.stderr}")
        delay = base_delay * 2 ** (attempt - 1)
        print(
            f"gh failed (attempt {attempt}/{attempts}), retrying in {delay:g}s: "
            f"{(r.stderr or '').strip()[:200]}",
            file=sys.stderr,
        )
        time.sleep(delay)
    raise AssertionError("unreachable: run_gh returns or raises on every attempt")


def main() -> None:
    os.makedirs(ROOT, exist_ok=True)

    print(f"Fetching issue list from {REPO} (state=all, limit 1000) ...")
    r = run_gh(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            REPO,
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            # `updatedAt` is consumed by fetch_events.py, which refuses to trust a cached
            # events file older than the issue's last update. Dropping it here silently
            # disables that guard, because the check falls back to "no timestamp -> trust
            # the cache" and every relabelled issue keeps its stale event history.
            # `body` and `closedByPullRequestsReferences` ride on this one paginated call
            # so fetch_bodies.py can build issue_extra.json without a `gh issue view`
            # per issue.
            "number,title,state,stateReason,createdAt,closedAt,updatedAt,labels,comments,body,closedByPullRequestsReferences",
        ]
    )

    issues = json.loads(r.stdout)
    with open(f"{ROOT}/issues.json", "w") as f:
        json.dump(issues, f)

    print(f"Wrote {len(issues)} issues to {ROOT}/issues.json")
    if len(issues) >= 1000:
        print(
            "WARNING: the issue list hit the 1000-issue cap; older issues are missing "
            "and every count in the dashboard is a floor. Raise --limit in fetch_issues.py."
        )


if __name__ == "__main__":
    main()
