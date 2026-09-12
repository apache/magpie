<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #5510
Author: eric-contributor
AuthorAssociation: CONTRIBUTOR
CreatedAt: 2026-05-11T10:00:00Z
IsDraft: false
Mergeable: MERGEABLE
Labels: []
StatusCheckRollup: SUCCESS
UnresolvedThreads: 1
UnresolvedThreadReviewers: ["kaxil"]
LastCommitDate: 2026-05-15T08:00:00Z
Viewer: potiuk
Now: 2026-05-18T10:00:00Z

Comments:
  (none)

ReviewThreadComments:
  - author: kaxil (MEMBER), createdAt: 2026-05-17T14:00:00Z
    body: "Could we avoid the extra round-trip here? The retry wrapper
    should reuse the existing connection instead of opening a new one."

LatestReviews:
  (none)
