#!/usr/bin/env python3
"""Dump the security-team roster (tracker repo's collaborators) to <cache>/roster.txt."""

import os
import subprocess

ROOT = os.environ.get('TRACKER_STATS_CACHE', '/tmp/tracker-stats-cache')
REPO = os.environ.get('TRACKER_STATS_REPO', 'airflow-s/airflow-s')

os.makedirs(ROOT, exist_ok=True)

r = subprocess.run(
    ['gh', 'api', f'repos/{REPO}/collaborators', '--jq', '.[].login', '--paginate'],
    capture_output=True, text=True, timeout=60,
)
if r.returncode != 0:
    raise SystemExit(f"gh failed: {r.stderr}")

logins = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
with open(f'{ROOT}/roster.txt', 'w') as f:
    for ln in sorted(set(logins)):
        f.write(ln + '\n')

print(f"Wrote {len(set(logins))} roster handles to {ROOT}/roster.txt")
