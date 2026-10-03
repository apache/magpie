<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #331:

number: 331
title: "[Security Report] Apache Airflow: Path traversal in log file download endpoint (split from #301) [GHSA-7f3x-9q2m-hv4c]"
state: OPEN
labels: security issue, airflow, cve allocated, pr created
milestone: Airflow 3.2.2
assignees: [jsmith]
body: |
  ### The issue description

  The task-log download endpoint joins the user-supplied file name onto the
  log directory without normalising it, so an authenticated user with log-read
  permission can read files outside the log directory.

  ### Reporter credited as

  Maria Faria

  ### Severity

  Medium

  ### CWE

  CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')

  ### Affected versions

  `< 3.2.2`

  ### Short public summary for publish

  When remote logging is disabled, an authenticated user with log-read
  permission could read arbitrary files readable by the webserver through the
  log download endpoint. Users are advised to upgrade to Airflow 3.2.2.

  ### Security mailing list thread

  https://lists.apache.org/thread/9a8b7c6d5e4f

  ### PR with the fix

  https://github.com/apache/airflow/pull/52344

comments:
  - author: jsmith (security team)
    body: "Split this out of airflow-s/airflow-s#301, which covered two separate
      root causes. The GHSA relay re-imported it with the GHSA ID appended to
      the title."

Mail thread excerpts (security@airflow.apache.org, thread 9a8b7c6d5e4f):

  - From: Maria Faria <maria@example.com> — "Credit as Maria Faria please."
