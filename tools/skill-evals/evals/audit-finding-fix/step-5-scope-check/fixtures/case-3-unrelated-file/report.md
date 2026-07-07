<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Confirmed batch:
  mypy:ANN201:airflow/api/common/mark_tasks.py:47 — add return type annotation

Diff (git diff --stat):
  airflow/api/common/mark_tasks.py | 2 +-
  airflow/api/common/delete_dag.py | 3 ++-

Diff content:
--- a/airflow/api/common/mark_tasks.py
+++ b/airflow/api/common/mark_tasks.py
@@ -44,7 +44,7 @@
-def mark_task_instance_state(task_id, dag_id, run_id, state):
+def mark_task_instance_state(task_id, dag_id, run_id, state) -> None:

--- a/airflow/api/common/delete_dag.py
+++ b/airflow/api/common/delete_dag.py
@@ -18,6 +18,9 @@
+def _validate_dag_id(dag_id: str) -> bool:
+    """Validate that dag_id conforms to naming rules."""
+    return bool(re.match(r'^[a-zA-Z0-9_\-\.]+$', dag_id))

Note: `delete_dag.py` was not in the confirmed finding batch.
