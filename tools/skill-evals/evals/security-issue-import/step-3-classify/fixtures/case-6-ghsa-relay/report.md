<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: notifications@github.com
To: security@airflow.apache.org
Subject: [apache/airflow] Unauthenticated read of task instance logs via
 /api/v1/taskInstances endpoint (GHSA-4x8m-9q2r-vp3w)

A security researcher filed a GitHub Security Advisory against apache/airflow.

**Summary**

The `/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}/logs`
endpoint does not enforce authentication when the Airflow webserver is
configured with `auth_backend = airflow.api.auth.backend.deny_all` overridden
at the route level. An unauthenticated attacker with network access to the
webserver can read full task execution logs, which may contain secrets injected
via environment variables or XCom values.

**Affected versions**

Apache Airflow >= 2.8.0, tested on 2.9.4.

**Proof of concept**

```bash
curl -s http://<airflow-host>/api/v1/dags/my_dag/dagRuns/manual_2024-01-01/\
taskInstances/my_task/logs/1
```

Returns full log content with no credentials required.

---
You are receiving this because you are subscribed to this thread.
Reply to this email directly, view it on GitHub, or unsubscribe.
