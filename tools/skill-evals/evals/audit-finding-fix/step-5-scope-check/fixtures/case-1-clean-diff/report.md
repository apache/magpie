<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Confirmed batch:
  ruff:F401:airflow/models/xcom.py:5   — removed `import os` (unused)
  ruff:E501:airflow/models/xcom.py:89  — wrapped long line

Diff (git diff --stat):
  airflow/models/xcom.py | 4 ++--

Diff content:
--- a/airflow/models/xcom.py
+++ b/airflow/models/xcom.py
@@ -2,7 +2,6 @@
 import json
-import os
 import pickle
 from typing import Any
@@ -86,7 +85,8 @@ class XCom(Base):
-        value = cls.serialize_value(value, key=key, task_id=task_id, dag_id=dag_id, run_id=run_id)
+        value = cls.serialize_value(
+            value, key=key, task_id=task_id, dag_id=dag_id, run_id=run_id
+        )
