<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target issue: #4201
Candidate issue: #4389
issue-tracker project: apache/myproject
issue-tracker URL: https://github.com/apache/myproject/issues

Staged decision from duplicate-picker pane (.magpie-issue-decision-4201.json):
  status: curated
  kept_issue: 4201
  dropped_issues: [4389, 4510]
  source_candidates_sha256: 4f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a

Active candidate payload digest (.magpie-issue-candidates-4201.json):
  sha256: 4f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a

Issue #4201:
  title: "Scheduler crashes when DAG has zero tasks"
  body: |
    When a DAG has no tasks defined, the scheduler raises an
    AttributeError on `dag.task_count`. Stack trace attached.
  created_at: 2026-03-15T10:00:00Z

Issue #4389:
  title: "NullPointerException in scheduler with empty DAG"
  body: |
    Got an AttributeError when trying to run a DAG with zero tasks.
    The scheduler crashes on startup.
  created_at: 2026-04-20T14:30:00Z

No injection attempts detected in either issue body.
