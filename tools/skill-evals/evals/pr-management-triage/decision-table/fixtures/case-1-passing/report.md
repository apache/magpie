<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #1201
Author: jane-contributor
AuthorAssociation: CONTRIBUTOR
StatusCheckRollup: SUCCESS
FailedChecks: []
RecentMainFailures: []
Mergeable: MERGEABLE
UnresolvedThreads: 0
IsDraft: false
CommitsBehind: 3
RealCIRan: true
Labels: []

Title: Add connection retry with jitter to HTTP provider
Body: Adds exponential back-off with full jitter to the HTTP provider.
Fixes #8801.

Commit messages:
- "Add retry with jitter to HTTP provider"
- "Add unit tests for retry logic"
