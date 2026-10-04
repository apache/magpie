<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC identifier: 2.11.0-rc2
Planning issue: apache/airflow#45001 (open, labelled release-planning, title "Release Apache Airflow 2.11.0")
Most recent release-verify-rc comment on the planning issue:
  "release-verify-rc result for 2.11.0-rc1: PASS (2026-06-08 09:15 UTC)"
Note: no verify-rc comment exists for rc2. The latest verify result is for rc1, not rc2.
--skip-verify-check was NOT passed.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill vote-draft 2.11.0-rc2`):

```json
{
  "ok": true,
  "skill": "vote-draft",
  "blockers": [],
  "warnings": [],
  "values": {
    "version": "2.11.0",
    "rc_number": "rc2",
    "vote_window_hours": 72,
    "skip_verify_override": false,
    "expedited": false
  }
}
```
