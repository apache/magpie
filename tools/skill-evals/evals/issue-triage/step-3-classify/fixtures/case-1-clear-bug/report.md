<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-99101
Title: SchedulerJob crashes with RecursionError when dag_bag has more than 1000 DAGs
Reporter: alice-dev
Status: Open
Component: scheduler
Filed: 2026-04-01

Body:
  When the scheduler starts with a dag_bag containing more than 1000 DAGs, it crashes immediately
  with a RecursionError. Reproduction steps:
  1. Create 1001 DAG files in your dags/ folder
  2. Start the scheduler: `airflow scheduler`
  3. Observe the crash

  Stack trace:
  ```text
  RecursionError: maximum recursion depth exceeded
    File "airflow/scheduler/scheduler_job.py", line 412, in _process_dags
    File "airflow/scheduler/scheduler_job.py", line 412, in _process_dags
    ...
  ```

  This worked fine in 2.8.0. Regression introduced in 2.9.0.

Comments:
  - maintainer-bob (MEMBER), 2026-04-02: "Confirmed — I can reproduce this on main with 1001 DAGs.
    The issue is in `_process_dags` which calls itself recursively without a depth guard."
