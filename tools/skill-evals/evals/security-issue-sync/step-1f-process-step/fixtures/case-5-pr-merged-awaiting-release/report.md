<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #231:

number: 231
title: "SQL injection via DAG run conf parameter"
state: OPEN
labels: airflow, cve allocated, pr merged
milestone: 3.0.3
assignees: [jsmith]
comments: []
body: |
  ### The issue description

  Unsanitized `conf` parameter allows SQL injection in the DAG run
  trigger endpoint.

  ### Reporter credited as

  Eve Researcher

  ### Severity

  High

  ### Affected versions

  3.0.0, 3.0.1, 3.0.2

  ### CVE tool link

  https://cveprocess.apache.org/cve5/CVE-2025-38291

  ### PR with the fix

  https://github.com/apache/airflow/pull/47183

PR state: merged
PR merged at: 2025-10-14T09:22:00Z
PR milestone: 3.0.3
Release 3.0.3 on PyPI: not yet published
