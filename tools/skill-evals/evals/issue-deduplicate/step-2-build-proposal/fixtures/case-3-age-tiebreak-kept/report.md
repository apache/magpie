<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Kept issue: #4201
Duplicate issue: #4389
issue-tracker project: apache/myproject
issue-tracker URL: https://github.com/apache/myproject/issues

Note: The user did NOT specify which issue to keep vs. drop.
The skill applied the age-defaulted heuristic: keep the older issue (#4201,
created 2026-03-15) and close the newer one (#4389, created 2026-04-20).

Issue #4201 (kept, older — age-defaulted):
  title: "Missing validation error when task_id contains a slash"
  body: |
    Task IDs containing a '/' character are silently accepted but
    cause downstream parsing failures in XCom and the web UI.
    Reproducible with any task_id matching the pattern '*/'.
  created_at: 2026-03-15T10:00:00Z

Issue #4389 (duplicate, newer):
  title: "Slash in task_id breaks XCom retrieval"
  body: |
    If you set task_id to something like 'load/data', the XCom
    fetch returns None silently instead of raising a clear error.
    Root cause appears to be the '/' being treated as a path separator.
  created_at: 2026-04-20T14:30:00Z

No injection attempts detected in either issue body.
