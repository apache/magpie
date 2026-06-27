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

"""Fetch createdAt + mergedAt + state for every upstream-repo PR referenced
by any tracker (via closedByPullRequestsReferences or body parse). Cache to
`<TRACKER_STATS_CACHE>/prs.json`.

The upstream repo is `$TRACKER_STATS_UPSTREAM_REPO` (default
`apache/airflow`); set to `none` / `""` to skip this fetch entirely."""

import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.environ.get("TRACKER_STATS_CACHE", "/tmp/tracker-stats-cache")
UPSTREAM = os.environ.get("TRACKER_STATS_UPSTREAM_REPO", "apache/airflow")
if UPSTREAM in ("", "none", "null"):
    print("TRACKER_STATS_UPSTREAM_REPO is empty/none - skipping PR fetch.")
    raise SystemExit(0)

EXTRA = f"{ROOT}/issue_extra.json"
OUT = f"{ROOT}/prs.json"

with open(EXTRA) as f:
    extra = json.load(f)

PR_PAT = re.compile(
    rf"{re.escape(UPSTREAM)}#(\d+)|https://github\.com/{re.escape(UPSTREAM)}/pull/(\d+)",
    re.I,
)


def extract_prs(v):
    nums = set()
    cb = v.get("closedByPullRequestsReferences") or []
    for ref in cb:
        if ref.get("repository", {}).get("nameWithOwner") == UPSTREAM:
            nums.add(ref["number"])
    body = v.get("body") or ""
    # Only parse the "PR with the fix" field portion if we can find it,
    # but also accept apache/airflow PR mentions anywhere in the body
    # (the spec allows either).
    for m in PR_PAT.findall(body):
        n = m[0] or m[1]
        if n:
            nums.add(int(n))
    return nums


# Build issue -> PR set + collect all unique PRs
issue_to_prs = {}
all_prs = set()
for issue_n, v in extra.items():
    prs = extract_prs(v)
    issue_to_prs[issue_n] = sorted(prs)
    all_prs.update(prs)

# Save the issue_to_prs linkage map alongside
with open(f"{ROOT}/issue_to_prs.json", "w") as f:
    json.dump(issue_to_prs, f)
print(f"unique {UPSTREAM} PRs to fetch: {len(all_prs)}")

# Resume support
cache = {}
if os.path.exists(OUT):
    with open(OUT) as f:
        cache = json.load(f)
    print(f"resume: {len(cache)} cached")

todo = [n for n in all_prs if str(n) not in cache]
print(f"to fetch: {len(todo)}")


def fetch(n):
    try:
        r = subprocess.run(
            ["gh", "pr", "view", str(n), "--repo", UPSTREAM, "--json", "number,createdAt,mergedAt,state"],
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
with ThreadPoolExecutor(max_workers=12) as ex:
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
errs = sum(1 for v in cache.values() if "error" in v)
print(f"done: cached {len(cache)} PRs ({errs} errors) → {OUT}")
