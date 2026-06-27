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

"""Fetch issue body + closedByPullRequestsReferences for every tracker
issue and cache to /tmp/claude/dashboard/issue_extra.json."""

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.environ.get("TRACKER_STATS_CACHE", "/tmp/tracker-stats-cache")
REPO = os.environ.get("TRACKER_STATS_REPO", "airflow-s/airflow-s")
OUT = f"{ROOT}/issue_extra.json"

with open(f"{ROOT}/issues.json") as f:
    issues = json.load(f)

# Resume support
cache = {}
if os.path.exists(OUT):
    with open(OUT) as f:
        cache = json.load(f)
    print(f"resume: {len(cache)} cached")

todo = [i["number"] for i in issues if str(i["number"]) not in cache]
print(f"to fetch: {len(todo)}")


def fetch(n):
    try:
        r = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(n),
                "--repo",
                REPO,
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


done = 0
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(fetch, n): n for n in todo}
    for fut in as_completed(futs):
        n, data = fut.result()
        cache[str(n)] = data
        done += 1
        if done % 25 == 0:
            with open(OUT, "w") as f:
                json.dump(cache, f)
            print(f"  {done}/{len(todo)}")

with open(OUT, "w") as f:
    json.dump(cache, f)
print(f"done: cached {len(cache)} → {OUT}")
