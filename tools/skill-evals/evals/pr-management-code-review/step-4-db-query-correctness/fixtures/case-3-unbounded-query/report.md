Title: Add endpoint returning task instances for the UI

Diff adds: airflow/api/task_instances.py

--- /dev/null
+++ b/airflow/api/task_instances.py
@@
+def all_task_instances(session):
+    # the returned list becomes the API response body
+    return [ti.as_dict() for ti in session.query(TaskInstance).all()]
