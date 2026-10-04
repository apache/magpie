<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Planning issue: apache/airflow#45010 (open, labelled `promoted`, title "Release Apache Airflow 2.11.0")
Planning issue body excerpt:
  Promote timestamp: 2026-06-10 08:00 UTC
  dist/release URL: https://dist.apache.org/repos/dist/release/airflow/2.11.0/
  Download Page: https://airflow.apache.org/docs/apache-airflow/2.11.0/installation/installing-from-pypi.html
  Changelog: https://github.com/apache/airflow/blob/2.11.0/CHANGELOG.md

Current UTC time: 2026-06-11 10:00 UTC
--skip-promote-wait was NOT passed.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill announce-draft 2.11.0 --promote-timestamp 2026-06-10T08:00:00Z --download-page https://airflow.apache.org/docs/apache-airflow/2.11.0/installation/installing-from-pypi.html`):

```json
{
  "ok": true,
  "skill": "announce-draft",
  "blockers": [],
  "warnings": [],
  "values": {
    "version": "2.11.0",
    "skip_promote_wait_override": false,
    "non_asf": false,
    "promote_clear_after_utc": null,
    "promote_wait_active": false,
    "download_page_url": "https://airflow.apache.org/docs/apache-airflow/2.11.0/installation/installing-from-pypi.html",
    "release_announce_backend": "announce-list"
  }
}
```
