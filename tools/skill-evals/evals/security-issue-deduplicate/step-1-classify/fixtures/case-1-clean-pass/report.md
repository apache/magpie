<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #67 (drop tracker):

number: 67
title: "API: Server-side request forgery via connection test"
state: OPEN
labels: airflow
body: |
  ### The issue description

  The /api/v1/connections/test endpoint performs an HTTP request to the
  connection URL without allowlisting — any authenticated user can force
  the Airflow API server to connect to internal hosts.

  ### Reporter credited as

  Bob Researcher <bob@seclab.io>

  ### Severity

  Unknown

  ### Affected versions

  2.10.0
