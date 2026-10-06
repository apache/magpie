<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Title:** Viewer-role user can read XCom values of restricted DAGs via REST API

A user with the `Viewer` role and DAG-level access limited to `dag_a` can call:

    GET /api/v1/dags/dag_b/dagRuns/<run_id>/taskInstances/extract/xcomEntries/db_credentials

and receive the full XCom entry — including its value, which `dag_b` uses to
pass a database password between tasks — for `dag_b`, which the viewer has no
access to. The same user gets `403 Forbidden` from
`GET /api/v1/dags/dag_b/dagRuns`, so DAG-level access control is enforced
elsewhere; the XCom entry endpoint checks only the generic "read XCom"
permission and skips the per-DAG check.

Steps to reproduce:
1. Create a user with Viewer role, DAG access limited to `dag_a`.
2. Run `dag_b`, whose `extract` task pushes the XCom `db_credentials`.
3. Authenticate as the restricted user and call the XCom entry endpoint above.
4. Response contains the XCom value in plaintext.

Tested on Airflow 2.9.3. Relevant code: `airflow/api_connexion/endpoints/xcom_endpoint.py`.
