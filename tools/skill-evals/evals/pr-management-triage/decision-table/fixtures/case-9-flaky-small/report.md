PR #9403
Author: kate-contributor
AuthorAssociation: CONTRIBUTOR
StatusCheckRollup: FAILURE
FailedChecks: ["Pytest ARM"]
RecentMainFailures: []
Mergeable: MERGEABLE
UnresolvedThreads: 0
IsDraft: false
CommitsBehind: 8
RealCIRan: true
Labels: []

Title: Fix timezone handling in scheduler loop
Body: Ensures the scheduler loop uses UTC throughout and does not drift
when the system clock changes.
