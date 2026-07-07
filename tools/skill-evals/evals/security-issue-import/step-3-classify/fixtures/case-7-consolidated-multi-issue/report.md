<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: pen-tester@consulting.example
Subject: Multiple security vulnerabilities in Apache Airflow 2.10.x

Hi team,

During a recent engagement I found three unrelated security issues in Apache
Airflow. I've grouped them here for efficiency.

## Issue 1 — SSRF via connection test endpoint

The POST /api/v1/connections/test endpoint forwards requests to arbitrary
hosts. An authenticated user can use this to probe internal network services.
Affected: airflow/api_fastapi/execution_api/routes/connections.py

## Issue 2 — Stored XSS in DAG description field

The DAG description rendered in the UI at /dags/{dag_id}/details is not
HTML-escaped. A DAG author can inject arbitrary JavaScript that executes in
the browser of any user who views the DAG details page.
Affected: airflow/www/views.py

## Issue 3 — Scheduler log file path traversal

The log download endpoint at /log?filename= does not sanitise the filename
parameter, allowing directory traversal to read arbitrary files accessible
to the scheduler process.
Affected: airflow/utils/log/log_reader.py

All three tested on Airflow 2.10.1. Let me know if you need PoCs.

Regards,
Pat Tester
