<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Title:** Unauthenticated attacker can enumerate DAG run histories via REST API

The endpoint `GET /api/v1/dags/{dag_id}/dagRuns` does not enforce
authentication. With the webserver's API authentication enabled, every other
endpoint we tried (for example `GET /api/v1/dags`) returns `401 Unauthorized`
without credentials, but this one returns data.
An external attacker with network access to the webserver can enumerate all
DAG run histories — including task states, execution timestamps, and operator
parameters logged to the run record — without supplying any credentials.

Proof of concept:

```bash
curl -s http://<airflow-host>/api/v1/dags/production_etl/dagRuns
```

Returns a full JSON array of DAG run records with no Authorization header
required.

Tested on Airflow 2.9.1. Relevant code: `airflow/api_connexion/endpoints/dag_run_endpoint.py`.
