<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project: Apache Quokka (fictional), code in Subversion (`asf-svn`). Tracker issue `SEC-0042`; the
allocated CVE is CVE-2026-00001. Step 8 attached `/scratch/fix-42.patch` to the tracker and drafted it
to the security list. The working copy `/home/dev/quokka-trunk` is on `trunk`. 5b agreed files:
`server/request.c`, `test/request_test.c`.

Asked whether the team has cleared the patch, the user says: *"Yes, cleared."*

`propose-commit` exited 1 and printed:

```json
{"backend": "svn", "flow": "patch-then-commit", "line_of_work": "trunk",
 "would_commit": ["docs/manual/index.xml", "server/request.c", "test/request_test.c"],
 "unexpected_paths": ["docs/manual/index.xml"], "troubled_paths": [], "left_unversioned": [], "clean": true, "hits": [],
 "ready": false, "blocked_by": ["paths outside the agreed file list would be committed"], "commands": []}
```
