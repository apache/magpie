<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

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
