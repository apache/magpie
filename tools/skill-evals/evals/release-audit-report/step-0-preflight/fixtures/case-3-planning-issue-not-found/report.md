<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Trigger: /release-audit-report 2.12.0
(--planning-issue was NOT passed)

No planning issue found on apache/airflow matching "2.12.0" in its title.
(Search found issues for 2.11.0, 2.10.3, and 2.10.2 — none for 2.12.0.)

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill audit-report 2.12.0`):

```json
{
  "ok": true,
  "skill": "audit-report",
  "blockers": [],
  "warnings": [],
  "values": {
    "roster_path": "projects/airflow/pmc-roster.md",
    "version": "2.12.0",
    "audit_log_path": "audit-logs/releases"
  }
}
```
