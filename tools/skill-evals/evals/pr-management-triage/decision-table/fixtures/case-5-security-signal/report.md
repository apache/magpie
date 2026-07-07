<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #5601
Author: grace-contributor
AuthorAssociation: CONTRIBUTOR
StatusCheckRollup: SUCCESS
FailedChecks: []
RecentMainFailures: []
Mergeable: MERGEABLE
UnresolvedThreads: 0
IsDraft: false
CommitsBehind: 0
RealCIRan: true
Labels: []

Title: Fix SQL injection in connection string parser
Body: Adds parameterised queries to the connection string parser to
prevent user-controlled input from being interpolated into SQL.

Commit messages:
- "Fix connection string parser"
- "Add parameterised queries to parser test suite"
