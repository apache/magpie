<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #1220
Author: alex-contributor
AuthorAssociation: CONTRIBUTOR
StatusCheckRollup: SUCCESS
FailedChecks: []
RecentMainFailures: []
Mergeable: MERGEABLE
UnresolvedThreads: 0
IsDraft: false
CommitsBehind: 1
RealCIRan: true
Labels: []
ConfigOverrides:
  enable_typed_decision_prefilter: false

Title: Implement exponential backoff for S3 client
Body: Implements exponential backoff retry strategy for S3 client calls.
Fixes #9102.

Commit messages:
- "feat(s3): add exponential backoff retry strategy"
- "test(s3): add unit tests for backoff retry"
