<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Apply phase results:

1. gh issue edit 42 --body-file /tmp/merged-body.md → OK
2. Rollup upsert on #42 (Merge kept entry appended) → comment 9900001 updated
3. Rollup upsert on #67 (Merge dropped entry appended) → comment 9900002 updated
4. gh issue edit 67 --add-label duplicate → OK
5. gh issue close 67 --reason not-planned → OK
6. uv run generate-cve-json 42 --attach → CVE JSON attached at comment 9900003

Kept tracker: #42 — now carries both Alice Example and Bob Researcher credits,
both mailing-list threads, CVE-2024-12345 allocation unchanged.
Dropped tracker: #67 — closed as not planned, labelled duplicate.
No blockers surfaced.
