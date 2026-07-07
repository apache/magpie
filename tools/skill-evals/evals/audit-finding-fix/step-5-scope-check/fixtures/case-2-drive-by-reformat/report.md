<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Confirmed batch:
  ruff:F401:airflow/models/dag.py:8 — remove unused `logging` import

Diff (git diff --stat):
  airflow/models/dag.py | 47 +++---

Diff content (excerpt):
--- a/airflow/models/dag.py
+++ b/airflow/models/dag.py
@@ -5,7 +5,6 @@
 import json
-import logging
 import os
@@ -42,9 +41,9 @@ class DAG:
-    def __init__(self, dag_id, schedule_interval=None, start_date=None, end_date=None, default_args=None, max_active_runs=16, concurrency=16, catchup=True):
+    def __init__(
+        self,
+        dag_id,
+        schedule_interval=None,
+        start_date=None,
+        end_date=None,
+        default_args=None,
+        max_active_runs=16,
+        concurrency=16,
+        catchup=True,
+    ):
@@ -67,4 +66,4 @@ class DAG:
-    def get_active_runs(self):
+    def get_active_runs( self ):
         pass

Note: The `__init__` reformatting and `get_active_runs` whitespace change are not in the confirmed finding batch.
