<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #318:

number: 318
title: "Connection test endpoint allows SSRF to internal metadata services"
state: OPEN
labels: security issue, airflow, cve allocated, pr merged
milestone: Airflow 3.2.2
assignees: [jsmith]
body: |
  ### The issue description

  The HTTP connection test endpoint follows redirects to link-local addresses,
  letting an authenticated UI user with connection-edit permission reach the
  cloud metadata service from the webserver.

  ### Reporter credited as

  Carol Tester

  ### Severity

  Medium

  ### CWE

  CWE-918: Server-Side Request Forgery (SSRF)

  ### Affected versions

  `>= 3.1.0, < 3.2.2`

  ### Short public summary for publish

  When the connection test feature is enabled, an authenticated user with
  connection-edit permission could make the Airflow webserver issue requests
  to internal addresses. Users are advised to upgrade to Airflow 3.2.2.

  ### Security mailing list thread

  https://lists.apache.org/thread/abc123def456

  ### PR with the fix

  https://github.com/apache/airflow/pull/52210

comments:
  - author: jsmith (security team)
    body: "Fix PR apache/airflow#52210 is merged and targets v3-1-test, so I set
      Affected versions to start at 3.1.0, the oldest line the fix ships on."
  - author: mwilson (security team)
    body: "Sounds good. Backport to 3.2.2 confirmed, milestone set."

Mail thread excerpts (security@airflow.apache.org, thread abc123def456):

  - From: Carol Tester <carol@example.org> — "Please credit me as Carol Tester. Happy with the fix."
