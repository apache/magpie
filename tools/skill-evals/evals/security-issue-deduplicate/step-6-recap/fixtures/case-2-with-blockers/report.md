<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Apply phase results:

1. gh issue edit 55 --body-file /tmp/merged-body.md → OK
2. Rollup upsert on #55 (Merge kept entry appended) → comment 9900010 updated
3. Rollup upsert on #71 (Merge dropped entry appended) → comment 9900011 updated
4. gh issue edit 71 --add-label duplicate → OK
5. gh issue close 71 --reason not-planned → OK
6. uv run generate-cve-json 55 --attach → CVE JSON attached at comment 9900012

Kept tracker: #55 — carries Carol Dev and Dave Security credits.
Dropped tracker: #71 — closed as not planned, labelled duplicate.

Blockers surfaced during merge:
- CWE conflict: kept tracker has CWE-502, dropped tracker has CWE-94.
  Triager must resolve before CVE JSON is finalised.
- Credit preference for Dave Security (drop reporter) not yet confirmed —
  send confirmation request before advisory publication.
