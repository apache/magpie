<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Thread: Issue #4612 — "Scheduler stalls after metadata DB migration"
ThreadType: issue
authorAssociation: FIRST_TIMER
Author: new-contributor-b
PriorWelcomePosted: true
MaintainerEngaged: false
OutOfScopeTopics: [security, CVE, deprecation, licensing, architecture]

Opening body:
"After migrating the metadata DB to PostgreSQL 16, the scheduler
starts but stalls at the first task and never progresses. No errors
in the logs."
