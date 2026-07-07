<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-99101 — SchedulerJob RecursionError with 1000+ DAGs

Maintainer comment by potiuk (MEMBER):
  "The issue is in `_process_dags` in airflow/scheduler/scheduler_job.py
   which calls itself recursively without a depth guard. Line ~412."

No stack trace available (crash on startup).
