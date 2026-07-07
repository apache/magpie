<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #287:

number: 287
title: "SSRF via connection test endpoint"
state: OPEN
labels: airflow, needs triage
milestone: null
assignees: [jsmith]
comments:
  - author: jsmith
    body: "Confirmed the endpoint does reach out to the supplied URL. Need to assess
      whether an allowlist approach or full disabling is the right fix."
  - author: mwilson
    body: "I think disabling unauthenticated access might be simpler. Let me check the
      upstream code."
body: |
  ### The issue description

  The connection test endpoint proxies HTTP to attacker-supplied URLs.

  ### Reporter credited as

  Bob Researcher

  ### Severity

  High

  ### Affected versions

  2.9.x, 2.10.0

  ### CVE tool link

  _No response_

  ### PR with the fix

  _No response_
