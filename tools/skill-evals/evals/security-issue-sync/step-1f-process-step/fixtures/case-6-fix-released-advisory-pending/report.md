<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #219:

number: 219
title: "Path traversal in log endpoint allows arbitrary file read"
state: OPEN
labels: airflow, cve allocated, fix released
milestone: 3.0.2
assignees: [rmgr]
comments: []
body: |
  ### The issue description

  The /log endpoint does not sanitize dag_id/task_id, allowing path
  traversal.

  ### Reporter credited as

  Frank Pentester

  ### Severity

  High

  ### Affected versions

  2.10.x, 3.0.0, 3.0.1

  ### CVE tool link

  https://cveprocess.apache.org/cve5/CVE-2025-29047

  ### PR with the fix

  https://github.com/apache/airflow/pull/46091

PR state: merged
PR merged at: 2025-09-02T11:15:00Z
Release 3.0.2 on PyPI: published 2025-09-10
Advisory sent: not yet
