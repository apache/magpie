<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Diff against main:

diff --git a/airflow/models/xcom.py b/airflow/models/xcom.py
--- a/airflow/models/xcom.py
+++ b/airflow/models/xcom.py
@@ -139,7 +139,10 @@ class XCom(Base):
     @classmethod
     def serialize_value(cls, value):
-        return json.dumps(result).encode("UTF-8")
+        if isinstance(value, bytes):
+            return value
+        return json.dumps(result).encode("UTF-8")

diff --git a/tests/models/test_xcom.py b/tests/models/test_xcom.py
--- a/tests/models/test_xcom.py
+++ b/tests/models/test_xcom.py
@@ -50,3 +50,8 @@ class TestXCom:
+    def test_serialize_bytes_value(self):
+        """AIRFLOW-88101: bytes values should be stored without JSON serialization."""
+        result = XCom.serialize_value(b"test")
+        assert result == b"test"
