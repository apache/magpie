<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Show dag model fields in the web view

Diff modifies: airflow/www/views.py

--- a/airflow/www/views.py
+++ b/airflow/www/views.py
@@
+from airflow.core.models import DagModel
+
 def dag_detail(dag_id):
-    ...
+    dag = DagModel.get(dag_id)
+    return render(dag)
