<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC identifier: 2.11.0-rc2
Planning issue: apache/airflow#46100 (open, labelled `vote-open`, title "Release Apache Airflow 2.11.0")
Planning issue body excerpt:
  [VOTE] thread opened: 2026-06-10 10:00 UTC
  [VOTE] thread URL: https://lists.apache.org/thread/abc123

Current UTC time: 2026-06-14 12:00 UTC
--force-close was NOT passed.
No previous partial-run AMBIGUOUS note on the planning issue.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill vote-tally 2.11.0-rc2 --vote-opened 2026-06-10T10:00:00Z`):

```json
{
  "ok": true,
  "skill": "vote-tally",
  "blockers": [],
  "warnings": [],
  "values": {
    "roster_path": "projects/airflow/pmc-roster.md",
    "version": "2.11.0",
    "rc_number": "rc2",
    "force_close": false,
    "mechanism": "dev-list-vote",
    "is_asf": true,
    "window_hours": 72,
    "elapsed_hours": 98.0,
    "window_closes_utc": "2026-06-13T10:00:00Z"
  }
}
```
