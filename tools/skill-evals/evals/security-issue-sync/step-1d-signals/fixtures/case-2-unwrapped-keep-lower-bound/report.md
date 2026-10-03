<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #324 (raw body as returned by `gh issue view --json body`):

number: 324
title: "Deferred trigger payload deserialized without type allow-list"
state: OPEN
labels: security issue, airflow, cve allocated, pr created
milestone: Airflow 3.2.2
assignees: [mwilson]
body: |
  ### The issue description

  Trigger payloads stored for deferred tasks are deserialized by the triggerer
  without restricting the allowed types, so a DAG author can run code in the
  triggerer process.

  ### Reporter credited as

  Bram Ouellet

  ### Severity

  High

  ### CWE

  CWE-502: Deserialization of Untrusted Data

  ### Affected versions

  >= 3.1.0, < 3.2.2

  ### Short public summary for publish

  When deferrable operators are used, a DAG author could execute code in the
  triggerer process through a crafted trigger payload. Users are advised to
  upgrade to Airflow 3.2.2.

  ### Security mailing list thread

  https://lists.apache.org/thread/f00dfeed7788

  ### PR with the fix

  https://github.com/apache/airflow/pull/52301

comments:
  - author: mwilson (security team)
    body: "Root cause traced: the vulnerability was introduced in 3.1.0 by
      apache/airflow#45678, which added the generic trigger-payload serializer.
      2.x and 3.0.x use the old typed path and are not affected."
  - author: jsmith (security team)
    body: "Agreed with the bisect. Fix PR is apache/airflow#52301, still in review."

Mail thread excerpts (security@airflow.apache.org, thread f00dfeed7788):

  - From: Bram Ouellet <bram@example.net> — "Credit as Bram Ouellet, thanks."
