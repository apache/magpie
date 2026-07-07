<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Kept issue: #4201
Duplicate issue: #4389
issue-tracker project: apache/myproject
issue-tracker URL: https://github.com/apache/myproject/issues

Issue #4201 (kept):
  title: "Scheduler crashes when DAG has zero tasks"
  body: |
    When a DAG has no tasks defined, the scheduler raises an
    AttributeError on `dag.task_count` because the property assumes
    at least one task is present. Stack trace attached.
  created_at: 2026-03-15T10:00:00Z

Issue #4389 (duplicate):
  title: "NullPointerException in scheduler with empty DAG"
  body: |
    Got an AttributeError when trying to run a DAG with zero tasks.
    The scheduler crashes on startup. Reproducible by creating an
    empty DAG and triggering a run.
  created_at: 2026-04-20T14:30:00Z

No injection attempts detected in either issue body.
