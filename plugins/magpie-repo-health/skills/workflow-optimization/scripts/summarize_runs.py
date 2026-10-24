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

"""Summarise GitHub Actions run and job TSVs for the workflow-optimization skill.

Runs TSV columns: name, event, conclusion, created_at, run_started_at, updated_at.
Jobs TSV columns: name, created_at, started_at, completed_at.
Both are what the `gh api ... --jq '...|@tsv'` calls in SKILL.md Step 1 print.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Conclusions that mean the workflow did its job or was deliberately not run.
NOT_FAILED = {"success", "skipped", "cancelled", "neutral", "action_required", ""}
# A workflow failing at least this share of its finished runs is flagged.
FAILING_SHARE = 0.5
# Jobs shorter than this many seconds are candidates for consolidation.
SHORT_JOB_SECONDS = 120


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _rows(path: Path, width: int) -> list[list[str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < width:
            fields += [""] * (width - len(fields))
        rows.append(fields[:width])
    return rows


def summarize_runs(rows: list[list[str]]) -> str:
    per_trigger: Counter[tuple[str, str]] = Counter()
    finished: Counter[str] = Counter()
    failed: Counter[str] = Counter()
    for name, event, conclusion, *_ in rows:
        per_trigger[(name, event)] += 1
        if conclusion:
            finished[name] += 1
            if conclusion not in NOT_FAILED:
                failed[name] += 1
    out = [f"runs: {len(rows)}", "", "runs per workflow and event:"]
    for (name, event), count in per_trigger.most_common():
        out.append(f"  {count:5d}  {name}  [{event}]")
    flagged = [
        (name, failed[name], finished[name])
        for name in finished
        if failed[name] and failed[name] / finished[name] >= FAILING_SHARE
    ]
    out += ["", "failing repeatedly (failed / finished):"]
    out += [f"  {f}/{n}  {name}" for name, f, n in sorted(flagged)] or ["  none"]
    return "\n".join(out)


def summarize_jobs(rows: list[list[str]]) -> str:
    out = ["job  run-time  queue-time"]
    run_times = []
    for name, created, started, completed in rows:
        c, s, d = _parse(created), _parse(started), _parse(completed)
        if not (c and s and d):
            out.append(f"  {name}: incomplete timestamps")
            continue
        run, queue = (d - s).total_seconds(), (s - c).total_seconds()
        run_times.append(run)
        flag = "  <- short" if run < SHORT_JOB_SECONDS else ""
        out.append(f"  {name}  {run / 60:.1f}m  {queue / 60:.1f}m{flag}")
    if run_times:
        short = sum(1 for t in run_times if t < SHORT_JOB_SECONDS)
        out += [
            "",
            f"jobs: {len(run_times)}, median run {statistics.median(run_times) / 60:.1f}m, "
            f"short (<{SHORT_JOB_SECONDS // 60}m): {short}",
        ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path, help="TSV file from SKILL.md Step 1")
    parser.add_argument("--jobs", action="store_true", help="the file holds jobs, not runs")
    args = parser.parse_args(argv)
    if not args.path.is_file():
        print(f"no such file: {args.path}", file=sys.stderr)
        return 2
    if args.jobs:
        print(summarize_jobs(_rows(args.path, 4)))
    else:
        print(summarize_runs(_rows(args.path, 6)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
