<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Simplify create_dag signature

Diff modifies: airflow/api/client.py  (public client API)

--- a/airflow/api/client.py
+++ b/airflow/api/client.py
@@
-def create_dag(dag_id, schedule="@daily", tags=None):
+def create_dag(dag_id, tags=None):
     ...

The `schedule` parameter is removed. create_dag is part of the public
client API used by downstream callers. No deprecation is provided.
