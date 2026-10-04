<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC identifier: 2.11.0-rc1
Planning issue: apache/airflow#45001 (open, labelled release-planning, title "Release Apache Airflow 2.11.0")
Most recent release-verify-rc comment on the planning issue:
  "release-verify-rc result for 2.11.0-rc1: PASS (2026-06-10 14:32 UTC)"

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill vote-draft 2.11.0-rc1`):

```json
{
  "ok": true,
  "skill": "vote-draft",
  "blockers": [],
  "warnings": [],
  "values": {
    "version": "2.11.0",
    "rc_number": "rc1",
    "vote_window_hours": 72,
    "skip_verify_override": false,
    "expedited": false
  }
}
```
