<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #198:

number: 198
title: "SSRF via connection test endpoint"
state: OPEN
labels: airflow, cve allocated, fix released, announced
milestone: 3.0.1
assignees: [rmgr]
comments: []
body: |
  ### The issue description

  Arbitrary SSRF via the connection test endpoint.

  ### Reporter credited as

  Alice Researcher

  ### Severity

  Medium

  ### Affected versions

  2.9.x, 3.0.0

  ### CVE tool link

  https://cveprocess.apache.org/cve5/CVE-2025-21044

  ### Public advisory URL

  https://lists.apache.org/thread/xyz123abc

  ### PR with the fix

  https://github.com/apache/airflow/pull/45012

cve.org API check:
  state: RESERVED
  (propagation from CNA tool to cve.org not yet complete)
