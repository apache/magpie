<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-rc-cut 2.12.0 rc1

Planning issue: apache/airflow#47000 (open, labelled `release-planning`,
title "Release Apache Airflow 2.12.0")
Planning issue body excerpt:
  Prep PR: apache/airflow#46990 — MERGED

RC tag check: gh api repos/apache/airflow/git/refs/tags/2.12.0-rc1 → 200
  The tag 2.12.0-rc1 already exists on the remote (previous cut attempt).

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill rc-cut 2.12.0 rc1`):

```json
{
  "ok": true,
  "skill": "rc-cut",
  "blockers": [],
  "warnings": [],
  "values": {
    "version": "2.12.0",
    "rc_number": "rc1",
    "archive_reviewed": true,
    "allow_unreviewed_archive": false,
    "signing_mode": "rm-key",
    "staging_url": "https://dist.apache.org/repos/dist/dev/airflow/2.12.0-rc1/",
    "rc_tag": "2.12.0-rc1"
  }
}
```
