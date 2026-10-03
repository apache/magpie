<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #337:

number: 337
title: "Apache Airflow: XSS (HUNTR-58213)"
state: OPEN
labels: security issue, airflow, cve allocated
milestone: Airflow 3.2.2
assignees: [mwilson]
body: |
  ### The issue description

  The DAG documentation panel renders `doc_md` without sanitising embedded
  HTML, so a DAG author can run script in the browser of any user who opens
  the DAG details page.

  ### Reporter credited as

  Tomas Lindqvist

  ### Severity

  Low

  ### CWE

  CWE-79: Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')

  ### Affected versions

  `< 3.2.2`

  ### Short public summary for publish

  When a DAG defines `doc_md` content, a DAG author could execute script in
  the browser of users viewing the DAG details page. Users are advised to
  upgrade to Airflow 3.2.2.

  ### Security mailing list thread

  https://lists.apache.org/thread/1122aabbccdd

  ### PR with the fix

  _No response_

comments:
  - author: mwilson (security team)
    body: "CVE allocated. Imported from the huntr relay, hence the ID in the title."

Mail thread excerpts (security@airflow.apache.org, thread 1122aabbccdd):

  - From: Tomas Lindqvist <tomas@example.se> — "Fine to credit me as Tomas Lindqvist."
