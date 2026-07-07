<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #3408
Author: eve-contributor
AuthorAssociation: CONTRIBUTOR
StatusCheckRollup: FAILURE
FailedChecks: ["Pytest MySQL", "Pytest SQLite"]
RecentMainFailures: ["Pytest MySQL", "Pytest SQLite"]
Mergeable: MERGEABLE
UnresolvedThreads: 0
IsDraft: false
CommitsBehind: 2
RealCIRan: true
Labels: []

Title: Add Airflow variable caching
Body: Caches Variable.get() results to reduce database round trips.

Commit messages:
- "Add Airflow variable caching with TTL"
- "Add tests for variable cache invalidation"
