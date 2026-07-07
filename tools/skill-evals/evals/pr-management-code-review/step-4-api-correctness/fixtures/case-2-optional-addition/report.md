<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Allow create_dag to set a description

Diff modifies: airflow/api/client.py  (public client API)

--- a/airflow/api/client.py
+++ b/airflow/api/client.py
@@
-def create_dag(dag_id, schedule="@daily", tags=None):
+def create_dag(dag_id, schedule="@daily", tags=None, description=None):
     ...

A new optional `description` parameter with a default is added; existing
callers are unaffected.
