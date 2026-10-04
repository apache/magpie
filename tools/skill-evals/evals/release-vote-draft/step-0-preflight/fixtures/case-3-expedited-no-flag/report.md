<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC identifier: 2.10.4-rc1
Planning issue: apache/airflow#44800 (open, labelled release-planning, title "Release Apache Airflow 2.10.4 [security]")
Most recent release-verify-rc comment on the planning issue:
  "release-verify-rc result for 2.10.4-rc1: PASS (2026-06-11 08:00 UTC)"
--expedited was NOT passed.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill vote-draft 2.10.4-rc1`):

```json
{
  "ok": false,
  "skill": "vote-draft",
  "blockers": [
    "vote_window_hours (48) is below the ASF 72-hour floor. Pass --expedited <reason> to proceed with an abbreviated window, or raise vote_window_hours to at least 72 in release-management-config.md."
  ],
  "warnings": [],
  "values": {
    "version": "2.10.4",
    "rc_number": "rc1",
    "vote_window_hours": 48,
    "skip_verify_override": false,
    "expedited": false
  }
}
```
