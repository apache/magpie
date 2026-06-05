Title: Tidy imports in emit module

Diff modifies: airflow/metrics/emit.py

--- a/airflow/metrics/emit.py
+++ b/airflow/metrics/emit.py
@@
-import statsd
-import logging
+import logging
+
+import statsd

Only import ordering and a blank line changed; no logic changed.
