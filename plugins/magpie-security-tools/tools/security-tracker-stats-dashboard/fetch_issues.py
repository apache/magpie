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
import tempfile

from gh_retry import run_gh

# The cache defaults under the platform temp root rather than a hardcoded `/tmp`:
# a sandboxed run is typically granted its own scratch directory and cannot write
# `/tmp`, so `/tmp/tracker-stats-cache` made the first fetch step fail outright.
# `tempfile.gettempdir()` honours `$TMPDIR` (POSIX) and `%TEMP%` (Windows).
ROOT = os.environ.get("TRACKER_STATS_CACHE") or os.path.join(tempfile.gettempdir(), "tracker-stats-cache")
REPO = os.environ.get("TRACKER_STATS_REPO", "airflow-s/airflow-s")


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
