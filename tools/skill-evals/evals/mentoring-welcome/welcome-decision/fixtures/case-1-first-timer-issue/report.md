<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Thread: Issue #4201 — "Connection pool exhausted after high-load test"
ThreadType: issue
authorAssociation: FIRST_TIMER
Author: new-contributor-a
PriorWelcomePosted: false
MaintainerEngaged: false
OutOfScopeTopics: [security, CVE, deprecation, licensing, architecture]

Opening body:
"I ran a load test against the scheduler and the connection pool became
exhausted after about 200 requests. The application returns 500 errors
and does not recover until restarted. Running version 2.9.0."
