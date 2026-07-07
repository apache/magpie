<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Reporter claims: An authenticated API user whose permissions are scoped to
a single DAG can call GET /api/v1/dags/{other_dag_id}/tasks via the Airflow
REST API and receive the full task list and parameters of a DAG they have no
explicit permission to access. The DAG-level access control is enforced on
the DAG list endpoint but not on the tasks sub-resource.

Attacker: Authenticated REST API user with DAG-scoped read permissions
  restricted to one DAG
Component: Airflow REST API, DAG-level authorization middleware
Effect: reads task configuration of DAGs outside the user's authorized scope
