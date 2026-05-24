#!/usr/bin/env python3
"""Dump all tracker issues (state=all, no PRs) to <cache>/issues.json."""

import json
import os
import subprocess

ROOT = os.environ.get('TRACKER_STATS_CACHE', '/tmp/tracker-stats-cache')
REPO = os.environ.get('TRACKER_STATS_REPO', 'airflow-s/airflow-s')

os.makedirs(ROOT, exist_ok=True)

print(f"Fetching issue list from {REPO} (state=all, limit 1000) ...")
r = subprocess.run(
    ['gh', 'issue', 'list', '--repo', REPO, '--state', 'all', '--limit', '1000',
     '--json', 'number,title,state,stateReason,createdAt,closedAt,labels,comments'],
    capture_output=True, text=True, timeout=300,
)
if r.returncode != 0:
    raise SystemExit(f"gh failed: {r.stderr}")

issues = json.loads(r.stdout)
with open(f'{ROOT}/issues.json', 'w') as f:
    json.dump(issues, f)

print(f"Wrote {len(issues)} issues to {ROOT}/issues.json")
