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
import subprocess

ROOT = os.environ.get("TRACKER_STATS_CACHE", "/tmp/tracker-stats-cache")
REPO = os.environ.get("TRACKER_STATS_REPO", "airflow-s/airflow-s")

os.makedirs(ROOT, exist_ok=True)

print(f"Fetching issue list from {REPO} (state=all, limit 1000) ...")
r = subprocess.run(
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
        "number,title,state,stateReason,createdAt,closedAt,labels,comments",
    ],
    capture_output=True,
    text=True,
    timeout=300,
)
if r.returncode != 0:
    raise SystemExit(f"gh failed: {r.stderr}")

issues = json.loads(r.stdout)
with open(f"{ROOT}/issues.json", "w") as f:
    json.dump(issues, f)

print(f"Wrote {len(issues)} issues to {ROOT}/issues.json")
