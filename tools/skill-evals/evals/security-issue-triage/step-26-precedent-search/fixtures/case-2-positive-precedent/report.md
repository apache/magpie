<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Current issue: #237
Title: "DAG-scoped API user can read XCom values from unauthorized DAGs"
Code pointer: airflow/api_fastapi/core_api/routes/public/xcom.py — get_xcom_entry()
Vulnerability class: cross-DAG data read by restricted authenticated user

### gh search issues — rejection precedents

No results.

### gh search issues — positive precedents

```json
[
  {
    "number": 201,
    "title": "DAG-scoped user can read task logs from other DAGs via REST",
    "labels": ["cve allocated"],
    "body_excerpt": "Code pointer: airflow/api_fastapi/core_api/routes/public/task_instances.py — get_task_instance_logs(). CVE-2025-43017 allocated. Same root cause: DAG-level authz not enforced on sub-resource reads."
  }
]
```

Match assessment: STRONG — same authz layer (DAG-scoped REST), same
vulnerability class (cross-DAG data read), adjacent code surface in the
same FastAPI router module.

Budget: 3 of 3 additional calls used.
