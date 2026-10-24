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

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import summarize_runs


class SummarizeRunsTest(unittest.TestCase):
    def test_counts_runs_per_workflow_and_event(self) -> None:
        rows = [
            ["Rust", "pull_request", "success", "", "", ""],
            ["Rust", "pull_request", "cancelled", "", "", ""],
            ["Rust", "merge_group", "success", "", "", ""],
        ]

        summary = summarize_runs.summarize_runs(rows)

        self.assertIn("    2  Rust  [pull_request]", summary)
        self.assertIn("    1  Rust  [merge_group]", summary)
        self.assertIn("failing repeatedly (failed / finished):\n  none", summary)

    def test_flags_workflow_failing_most_runs(self) -> None:
        rows = [["Fuzz", "schedule", "failure", "", "", ""]] * 4 + [
            ["Fuzz", "schedule", "success", "", "", ""]
        ]

        summary = summarize_runs.summarize_runs(rows)

        self.assertIn("  4/5  Fuzz", summary)

    def test_in_progress_runs_are_not_counted_as_finished(self) -> None:
        rows = [
            ["license", "pull_request", "", "", "", ""],
            ["license", "pull_request", "failure", "", "", ""],
        ]

        summary = summarize_runs.summarize_runs(rows)

        self.assertIn("  1/1  license", summary)


class SummarizeJobsTest(unittest.TestCase):
    def test_reports_run_and_queue_time_and_flags_short_jobs(self) -> None:
        rows = [
            ["lint", "2026-10-22T10:00:00Z", "2026-10-22T11:10:00Z", "2026-10-22T11:11:00Z"],
            ["test", "2026-10-22T10:00:00Z", "2026-10-22T10:05:00Z", "2026-10-22T10:25:00Z"],
        ]

        summary = summarize_runs.summarize_jobs(rows)

        self.assertIn("  lint  1.0m  70.0m  <- short", summary)
        self.assertIn("  test  20.0m  5.0m\n", summary + "\n")
        self.assertIn("jobs: 2, median run 10.5m, short (<2m): 1", summary)

    def test_incomplete_job_is_reported_not_dropped(self) -> None:
        summary = summarize_runs.summarize_jobs([["queued", "2026-10-22T10:00:00Z", "", ""]])

        self.assertIn("queued: incomplete timestamps", summary)


if __name__ == "__main__":
    unittest.main()
