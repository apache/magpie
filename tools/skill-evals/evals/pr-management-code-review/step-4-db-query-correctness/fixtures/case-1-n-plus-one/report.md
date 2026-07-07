<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add owner email to the dag-list response

Diff modifies: airflow/api/dag_list.py

--- a/airflow/api/dag_list.py
+++ b/airflow/api/dag_list.py
@@
 def list_dags(session):
-    dags = session.query(DagModel).limit(100).all()
-    return [{"dag_id": d.dag_id} for d in dags]
+    dags = session.query(DagModel).limit(100).all()
+    result = []
+    for dag in dags:
+        owner = session.query(User).filter(User.id == dag.owner_id).one()
+        result.append({"dag_id": dag.dag_id, "owner_email": owner.email})
+    return result
