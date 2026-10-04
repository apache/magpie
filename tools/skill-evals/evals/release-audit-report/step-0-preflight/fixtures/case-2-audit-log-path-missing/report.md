<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Trigger: /release-audit-report 2.11.0

Planning issue: apache/airflow#45200 (closed, title "Release Apache Airflow 2.11.0")

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill audit-report 2.11.0`):

```json
{
  "ok": false,
  "skill": "audit-report",
  "blockers": [
    "required key `audit_log_path` is missing from release-management-config.md"
  ],
  "warnings": [],
  "values": {
    "roster_path": "projects/airflow/pmc-roster.md",
    "version": "2.11.0",
    "audit_log_path": null
  }
}
```
