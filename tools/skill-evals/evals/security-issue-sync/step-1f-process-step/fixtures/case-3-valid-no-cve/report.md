<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #272:

number: 272
title: "Pickle deserialization via XCom crosses scheduler trust boundary"
state: OPEN
labels: airflow
milestone: null
assignees: [jsmith]
comments:
  - author: jsmith
    body: "Team consensus: this is valid. The pickle path crosses the dag-author /
      scheduler boundary which is the key trust boundary per the security model.
      CVE-worthy."
  - author: mwilson
    body: "+1, agree it is CVE-worthy."
body: |
  ### The issue description

  When the default XCom backend is in use, a DAG author can store a malicious
  pickled object that is deserialized by the scheduler worker.

  ### Reporter credited as

  Carol Tester

  ### Severity

  Unknown

  ### Affected versions

  2.8.0, 2.9.x

  ### CVE tool link

  _No response_

  ### PR with the fix

  _No response_
