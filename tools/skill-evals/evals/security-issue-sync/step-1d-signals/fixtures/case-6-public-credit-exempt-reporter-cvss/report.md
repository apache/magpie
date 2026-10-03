<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #349:

number: 349
title: "Stored script injection via rendered template fields"
state: OPEN
labels: security issue, airflow, needs triage
milestone: null
assignees: []
body: |
  ### The issue description

  Rendered template fields are shown in the task instance view without
  escaping, so a DAG author can inject script that runs in the browser of an
  operator who opens the rendered view.

  ### Reporter credited as

  Dana Whitfield

  ### Severity

  _No response_

  ### CWE

  _No response_

  ### Affected versions

  `< 3.2.2`

  ### Short public summary for publish

  _No response_

  ### Security mailing list thread

  https://lists.apache.org/thread/d4n4w0001 — Dana found this while running the
  Mythos scan for her employer and then reported it herself.

  ### PR with the fix

  _No response_

comments:
  - author: jsmith (security team)
    body: "Reporter rates this CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H (9.8,
      Critical). Let's just go with that for the Severity field."
  - author: mwilson (security team)
    body: "Independent read: this is stored XSS in the rendered-fields view, so
      CWE-79. Requires DAG-author access, which per our security model is
      already a trusted role, so I'd hold off on severity until we discuss."

Mail thread excerpts (security@airflow.apache.org, thread d4n4w0001):

  - From: Dana Whitfield <dana.whitfield@example.com> — "Hi, I'm Dana Whitfield.
    While running the Mythos scan at work I found a stored script injection in
    rendered template fields; full write-up is public at
    https://huntr.com/bounties/0f4e2c1a-7b55-4d0b-9a1e-3c2d1e0f9a88 . My CVSS
    3.1 estimate: AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H = 9.8 Critical. Please
    credit me as Dana Whitfield."
