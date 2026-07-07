<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Diff against main:

diff --git a/airflow/models/xcom.py b/airflow/models/xcom.py
--- a/airflow/models/xcom.py
+++ b/airflow/models/xcom.py
@@ -1,5 +1,5 @@
-import json, pickle
+import json
+import pickle
 from typing import Any
-from airflow.utils.session import  create_session
+from airflow.utils.session import create_session

@@ -139,3 +139,6 @@ class XCom(Base):
     def serialize_value(cls, value):
+        if isinstance(value, bytes):
+            return value
         return json.dumps(result).encode("UTF-8")

diff --git a/tests/models/test_xcom.py b/tests/models/test_xcom.py
+    def test_serialize_bytes_value(self):
+        assert XCom.serialize_value(b"test") == b"test"
