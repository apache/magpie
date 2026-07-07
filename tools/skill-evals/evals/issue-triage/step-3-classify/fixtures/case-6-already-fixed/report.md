<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-99606
Title: Pool slots not released after task timeout
Reporter: frank-ops
Status: Open
Component: scheduler
Filed: 2026-03-01

Body:
  When a task times out (execution_timeout exceeded), the pool slot it held is never released.
  This causes pools to fill up permanently until the scheduler is restarted.

Recent-fix scan results:
  - Commit abc1234 (2026-03-20, 19 days after filing): "Fix pool slot leak on task timeout"
    — touches airflow/models/pool.py and airflow/jobs/scheduler_job.py
    — commit message explicitly references AIRFLOW-99606
  - Issue-reproducer verdict: fixed-on-master — the pool slot is released correctly after
    the commit landed.

Comments:
  - frank-ops, 2026-04-01: "Can anyone check if this is fixed? I haven't heard back."
