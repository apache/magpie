<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC identifier: 2.11.0-rc2
Planning issue: apache/airflow#46100 (open, labelled `vote-open`, title "Release Apache Airflow 2.11.0")
Planning issue body excerpt:
  [VOTE] thread opened: 2026-06-14 08:00 UTC
  [VOTE] thread URL: https://lists.apache.org/thread/abc123

Current UTC time: 2026-06-14 12:00 UTC
--force-close was NOT passed.
No previous partial-run AMBIGUOUS note on the planning issue.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill vote-tally 2.11.0-rc2 --vote-opened 2026-06-14T08:00:00Z`):

```json
{
  "ok": false,
  "skill": "vote-tally",
  "blockers": [
    "vote window has not elapsed: 4 hours elapsed of 72-hour window (closes 2026-06-17T08:00:00Z)"
  ],
  "warnings": [],
  "values": {
    "roster_path": "projects/airflow/pmc-roster.md",
    "version": "2.11.0",
    "rc_number": "rc2",
    "force_close": false,
    "mechanism": "dev-list-vote",
    "is_asf": true,
    "window_hours": 72,
    "elapsed_hours": 4.0,
    "window_closes_utc": "2026-06-17T08:00:00Z"
  }
}
```
