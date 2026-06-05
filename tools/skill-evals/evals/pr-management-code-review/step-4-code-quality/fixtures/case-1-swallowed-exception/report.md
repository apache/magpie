Title: Best-effort metrics emit

Diff modifies: airflow/metrics/emit.py

--- a/airflow/metrics/emit.py
+++ b/airflow/metrics/emit.py
@@
 def emit(metric, value):
-    statsd.gauge(metric, value)
+    try:
+        statsd.gauge(metric, value)
+    except Exception:
+        pass
