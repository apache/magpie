<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Trigger: /release-promote 2.11.0-rc1
--planning-issue was NOT passed (auto-detect).
Resolved RM identity (from user.md): apache_id = johndoe

Planning issue: apache/airflow#45010 (open, labelled `vote-passed`, title "Release Apache Airflow 2.11.0")
Planning issue body excerpt:
  Staging URL: https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/
  [RESULT] [VOTE] archive: https://lists.apache.org/thread/some-result-thread-id

Target URL check: https://dist.apache.org/repos/dist/release/airflow/2.11.0/
  — directory ALREADY EXISTS and contains files:
    apache-airflow-2.11.0-source.tar.gz
    apache-airflow-2.11.0-source.tar.gz.asc
    apache-airflow-2.11.0-source.tar.gz.sha512
Note: the previous promote attempt may have partially landed, or a concurrent
session promoted the release. Manual inspection is required.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill promote 2.11.0-rc1 --rm johndoe`):

```json
{
  "ok": true,
  "skill": "promote",
  "blockers": [],
  "warnings": [],
  "values": {
    "roster_path": ".apache-magpie-overrides/pmc-roster.md",
    "rm_identity": "johndoe",
    "version": "2.11.0",
    "rc": "rc1",
    "non_asf": false,
    "rm_is_pmc": true,
    "dist_backend": "svnpubsub",
    "staging_url": "https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/",
    "target_url": "https://dist.apache.org/repos/dist/release/airflow/2.11.0/",
    "trusted_hardware_attestation_required": false,
    "handoff_non_pmc": false
  }
}
```
