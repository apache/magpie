<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Planning issue: apache/airflow#45010 (open, labelled `vote-passed`, title "Release Apache Airflow 2.11.0")
Note: the planning issue carries `vote-passed`, NOT `promoted`. The Step 10 promote step has not yet been confirmed.
The planning issue body carries no promote timestamp and no Download Page URL yet.

Current UTC time: 2026-06-11 10:00 UTC
--skip-promote-wait was NOT passed.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill announce-draft 2.11.0`):

```json
{
  "ok": false,
  "skill": "announce-draft",
  "blockers": [
    "promote timestamp unavailable: not in the planning issue body and --promote-timestamp was not passed",
    "Download Page URL unavailable: not in the planning issue body, not in the config, and --download-page was not passed"
  ],
  "warnings": [],
  "values": {
    "version": "2.11.0",
    "skip_promote_wait_override": false,
    "non_asf": false,
    "promote_clear_after_utc": null,
    "promote_wait_active": false,
    "download_page_url": null,
    "release_announce_backend": "announce-list"
  }
}
```
