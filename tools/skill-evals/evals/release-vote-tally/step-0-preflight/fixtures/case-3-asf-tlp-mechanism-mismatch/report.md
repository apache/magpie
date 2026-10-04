<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC identifier: 2.11.0-rc2
Planning issue: apache/airflow#46100 (open, labelled `vote-open`, title "Release Apache Airflow 2.11.0")
Planning issue body excerpt:
  [VOTE] thread opened: 2026-06-10 10:00 UTC
  [VOTE] discussion: https://github.com/apache/airflow/discussions/9001

Current UTC time: 2026-06-14 12:00 UTC
--force-close was NOT passed.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill vote-tally 2.11.0-rc2 --vote-opened 2026-06-10T10:00:00Z`):

```json
{
  "ok": false,
  "skill": "vote-tally",
  "blockers": [
    "an ASF project (project.md → organization: ASF) requires release_approval_mechanism=dev-list-vote; config has github-discussion"
  ],
  "warnings": [],
  "values": {
    "roster_path": "projects/airflow/pmc-roster.md",
    "version": "2.11.0",
    "rc_number": "rc2",
    "force_close": false,
    "mechanism": "github-discussion",
    "is_asf": true,
    "window_hours": 72,
    "elapsed_hours": 98.0,
    "window_closes_utc": "2026-06-13T10:00:00Z"
  }
}
```
