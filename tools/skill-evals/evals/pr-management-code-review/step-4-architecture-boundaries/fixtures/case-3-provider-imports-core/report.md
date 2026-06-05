Title: New HTTP hook

Diff adds: airflow/providers/http/hook.py

--- /dev/null
+++ b/airflow/providers/http/hook.py
@@
+from airflow.core.hooks import BaseHook
+
+class HttpHook(BaseHook):
+    ...
