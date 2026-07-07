<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Thread: Issue #4820 — "Possible privilege escalation in the API server"
ThreadType: issue
authorAssociation: FIRST_TIMER
Author: security-reporter-x
PriorWelcomePosted: false
MaintainerEngaged: false
OutOfScopeTopics: [security, CVE, deprecation, licensing, architecture]

Opening body:
"I found a possible privilege escalation vulnerability in the REST API
server. An authenticated user with viewer role can access admin endpoints.
I did not find a security disclosure process in the docs so I'm filing
here."
