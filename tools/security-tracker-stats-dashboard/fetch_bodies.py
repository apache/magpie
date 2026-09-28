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

"""Build <cache>/issue_extra.json (issue body + closedByPullRequestsReferences).

fetch_issues.py requests both fields on its single paginated `gh issue list`
call, so this step normally makes no network call at all: it copies the two
fields out of issues.json. The per-issue `gh issue view` path survives only as
a fallback for issues whose list entry lacks the fields (an issues.json written
by an older fetch_issues.py, or a gh too old to offer the field on `list`); it
keeps the original resume-from-cache semantics.
"""

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

EXTRA_FIELDS = ("body", "closedByPullRequestsReferences")


def extra_from_list(issue):
    """Return the issue_extra entry for a list-call issue, or None if the list lacks the fields."""
    if not all(k in issue for k in EXTRA_FIELDS):
        return None
    return {"number": issue["number"], **{k: issue[k] for k in EXTRA_FIELDS}}


def build_extra(issues, cache):
    """Merge list-call fields into *cache*; return the issue numbers still needing a per-issue fetch.

    List data is fresh on every run, so it overwrites any cached entry for the
    same issue. Issues without list data keep their cached entry and are only
    fetched when no cached entry exists.
    """
    todo = []
    for issue in issues:
        key = str(issue["number"])
        entry = extra_from_list(issue)
        if entry is not None:
            cache[key] = entry
        elif key not in cache:
            todo.append(issue["number"])
    return todo


def fetch(repo, n):
    try:
        r = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(n),
                "--repo",
                repo,
                "--json",
                "number,body,closedByPullRequestsReferences",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0:
            return n, {"error": r.stderr.strip()}
        return n, json.loads(r.stdout)
    except Exception as e:
        return n, {"error": str(e)}


def main():
    root = os.environ.get("TRACKER_STATS_CACHE", "/tmp/tracker-stats-cache")
    repo = os.environ.get("TRACKER_STATS_REPO", "airflow-s/airflow-s")
    out = f"{root}/issue_extra.json"

    with open(f"{root}/issues.json") as f:
        issues = json.load(f)

    # Resume support
    cache = {}
    if os.path.exists(out):
        with open(out) as f:
            cache = json.load(f)
        print(f"resume: {len(cache)} cached")

    todo = build_extra(issues, cache)
    print(f"from list call: {len(issues) - len(todo)}; to fetch per issue: {len(todo)}")

    done = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(fetch, repo, n): n for n in todo}
        for fut in as_completed(futs):
            n, data = fut.result()
            cache[str(n)] = data
            done += 1
            if done % 25 == 0:
                with open(out, "w") as f:
                    json.dump(cache, f)
                print(f"  {done}/{len(todo)}")

    with open(out, "w") as f:
        json.dump(cache, f)
    print(f"done: cached {len(cache)} → {out}")


if __name__ == "__main__":
    main()
