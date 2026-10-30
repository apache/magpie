<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #412:

number: 412
title: "Connection password exposed in task log on retry"
state: OPEN
labels: security issue, airflow, cve allocated
milestone: Airflow 3.2.2
assignees: [mwilson]
body: |
  ### The issue description

  When a task retries, the connection URI including the password is written
  to the task log without masking.

  ### Reporter credited as

  _No response_

  ### Severity

  Moderate

  ### CWE

  CWE-532: Insertion of Sensitive Information into Log File

  ### Affected versions

  `< 3.2.2`

  ### Short public summary for publish

  _No response_

  ### Security mailing list thread

  https://lists.apache.org/thread/r3tr7l0g01

  ### PR with the fix

  _No response_

comments:
  - author: mwilson (security team)
    body: "CVE allocated. Asked the reporter on the thread how they would like
      to be credited."

Mail thread excerpts (security@airflow.apache.org, thread r3tr7l0g01):

  - From: security team (mwilson) — "Thanks, we have allocated a CVE. How
    would you like to be credited in the advisory (name and, if applicable,
    affiliation), or would you prefer to remain anonymous?"
  - From: Lena Brandt <lena.brandt@example.org> — "Thanks for the quick
    turnaround. Please do not credit me — anonymous is fine."
