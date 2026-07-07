<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88404
Title: Scheduler becomes unresponsive after 48 hours of continuous operation

Body:
  After running the Airflow scheduler for approximately 48 hours without restart,
  it stops scheduling new task instances. No error is logged; the scheduler process
  is still alive but the heartbeat timestamp stops updating. Restarting the scheduler
  fixes the issue immediately.

  Environment: Airflow 2.9.1, PostgreSQL 15, Python 3.11, Kubernetes deployment.
