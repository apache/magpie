<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-99505
Title: Airflow should not require a metadata database
Reporter: skeptical-user
Status: Open
Component: core
Filed: 2026-04-18

Body:
  I shouldn't need to set up a Postgres or MySQL database just to run Airflow. The requirement
  for a metadata database is too heavy for simple use cases. Airflow should be able to run
  without any database.

Comments:
  - maintainer-eve (MEMBER), 2026-04-19:
    "The metadata database is a core architectural requirement — it stores DAG run state,
    task instances, XCom data, connections, and all scheduler coordination state. Airflow
    cannot function without it. This is documented at
    https://airflow.apache.org/docs/apache-airflow/stable/installation/prerequisites.html.
    For local development, sqlite is supported and requires no separate server."
