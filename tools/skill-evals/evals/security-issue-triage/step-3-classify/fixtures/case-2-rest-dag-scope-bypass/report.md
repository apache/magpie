<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Title:** Viewer-role user can read connections belonging to restricted DAGs via REST API

A user with the `Viewer` role and DAG-level access limited to `dag_a` can call:

    GET /api/v1/connections/prod_db_conn

and receive the full connection record — including the plaintext `password`
field — for `prod_db_conn`, which is used exclusively by `dag_b` that the
viewer has no explicit access to. The connections endpoint does not enforce
DAG-scoped access control; it checks only that the caller has the generic
"read connection" permission.

Steps to reproduce:
1. Create a user with Viewer role, DAG access limited to `dag_a`.
2. Create a connection `prod_db_conn` associated with `dag_b`.
3. Authenticate as the restricted user and call GET /api/v1/connections/prod_db_conn.
4. Response contains the connection password in plaintext.

Tested on Airflow 2.9.3. Relevant code: `airflow/api_fastapi/core_api/routes/connections.py`.
