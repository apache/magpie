#!/usr/bin/env python3
"""Fetch per-issue label-history events. Resumes from cache."""

import json
import subprocess
import concurrent.futures
import os

ROOT = os.environ.get('TRACKER_STATS_CACHE', '/tmp/tracker-stats-cache')
REPO = os.environ.get('TRACKER_STATS_REPO', 'airflow-s/airflow-s')
EVENTS_DIR = f'{ROOT}/events'

with open(f'{ROOT}/issues.json') as f:
    issues = json.load(f)

numbers = [i['number'] for i in issues]
print(f"Fetching events for {len(numbers)} issues...")

os.makedirs(EVENTS_DIR, exist_ok=True)

def fetch_one(n):
    out_path = f'{EVENTS_DIR}/{n}.json'
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return (n, True, 'cached')
    try:
        r = subprocess.run(
            ['gh', 'api', f'repos/{REPO}/issues/{n}/events',
             '--paginate',
             '--jq', '[.[] | select(.event == "labeled" or .event == "unlabeled" or .event == "closed" or .event == "reopened") | {event, label: (.label.name // null), created_at}]'],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode != 0:
            return (n, False, r.stderr[:200])
        out = r.stdout.strip()
        decoder = json.JSONDecoder()
        idx = 0
        merged = []
        while idx < len(out):
            while idx < len(out) and out[idx] in ' \n\r\t':
                idx += 1
            if idx >= len(out):
                break
            obj, n2 = decoder.raw_decode(out, idx)
            merged.extend(obj)
            idx = n2
        with open(out_path, 'w') as f:
            json.dump(merged, f)
        return (n, True, f'{len(merged)} events')
    except Exception as e:
        return (n, False, str(e)[:200])

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    results = list(ex.map(fetch_one, numbers))

ok = sum(1 for _, ok, _ in results if ok)
fail = [(n, msg) for n, ok, msg in results if not ok]
print(f"Done: {ok}/{len(numbers)} OK")
if fail:
    print("FAILURES:")
    for n, msg in fail[:20]:
        print(f"  #{n}: {msg}")
