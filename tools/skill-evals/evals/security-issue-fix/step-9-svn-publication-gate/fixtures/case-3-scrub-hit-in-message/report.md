<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project: Apache Quokka (fictional), code in Subversion (`asf-svn`). Tracker issue `SEC-0042`; the
allocated CVE is CVE-2026-00001. Step 8 attached `/scratch/fix-42.patch` to the tracker and drafted it
to the security list. The working copy `/home/dev/quokka-trunk` is on `trunk`. 5b agreed files:
`server/request.c`, `test/request_test.c`.

Asked whether the team has cleared the patch, the user says: *"Yes, cleared."*

The commit message reads `Fix CVE-2026-00001: reject request lines with an empty method token`.
`propose-commit` exited 1 and printed:

```json
{"backend": "svn", "flow": "patch-then-commit", "line_of_work": "trunk", "would_commit": ["server/request.c", "test/request_test.c"],
 "unexpected_paths": [], "troubled_paths": [], "left_unversioned": [], "clean": false,
 "hits": [{"surface": "message", "term": "CVE id", "match": "CVE-2026-00001", "line": 1, "file": null},
          {"surface": "message", "term": "CVE", "match": "CVE", "line": 1, "file": null}],
 "ready": false, "blocked_by": ["scrub hits"], "commands": []}
```
