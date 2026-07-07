<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #10040
Author: leo-contributor
AuthorAssociation: FIRST_TIME_CONTRIBUTOR
CreatedAt: 2026-04-20T09:00:00Z
IsDraft: true
Mergeable: MERGEABLE
Labels: []
StatusCheckRollup: null
UnresolvedThreads: 0
LastCommitDate: 2026-04-22T11:00:00Z
Viewer: potiuk
Now: 2026-05-18T10:00:00Z

Comments:
  - author: kaxil (COLLABORATOR), createdAt: 2026-05-14T10:00:00Z
    body: "I've been pairing with leo on this one. The approach we're
    taking is to replace the legacy connection pool with a new async
    implementation. The current draft already has the core logic in
    place — we just need to add the backpressure handling and the
    integration tests before marking it ready. Should be done this week."
