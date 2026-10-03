<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #342:

number: 342
title: "Unauthenticated access to the variable export endpoint"
state: OPEN
labels: security issue, airflow, cve allocated, pr created
milestone: Airflow 3.2.2
assignees: [jsmith]
body: |
  ### The issue description

  The variable export endpoint is missing its permission check, so any
  authenticated user can export all Airflow Variables, including ones holding
  credentials.

  ### Reporter credited as

  Priya Raman

  ### Severity

  High

  ### CWE

  CWE-862: Missing Authorization

  ### Affected versions

  `< 3.2.2`

  ### Short public summary for publish

  A Mythos scan flagged that, when the REST API is enabled, any authenticated
  user could export all Airflow Variables regardless of their permissions.
  Users are advised to upgrade to Airflow 3.2.2.

  ### Security mailing list thread

  https://lists.apache.org/thread/5c4n5c4n0001 — findings from the Mythos scan
  Contoso ran against Airflow; finding attributed to Priya Raman (Contoso AppSec).

  ### PR with the fix

  https://github.com/apache/airflow/pull/52377

comments:
  - author: jsmith (security team)
    body: "Status rollup: imported from the Contoso PSIRT batch (Mythos scan, finder
      Priya Raman per their spreadsheet). Fix PR apache/airflow#52377 open."

Mail thread excerpts (security@airflow.apache.org, thread 5c4n5c4n0001):

  - From: Contoso PSIRT <psirt@contoso.example> — "Attached are 4 findings from our
    Mythos scan of Apache Airflow 3.2.1. Finding #3 (variable export) was triaged
    by Priya Raman on our AppSec team."
  - From: jsmith (security team) — "Thanks, tracking finding #3 separately."
