<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Trigger: /release-promote 2.11.0-rc1
--planning-issue was NOT passed (auto-detect).
Resolved RM identity (from user.md): apache_id = johndoe

Planning issue: apache/airflow#45010 (open, labelled `vote-open`, title "Release Apache Airflow 2.11.0")
Note: the planning issue carries `vote-open`, NOT `vote-passed`. The Step 9
vote tally step has not yet been completed.

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
