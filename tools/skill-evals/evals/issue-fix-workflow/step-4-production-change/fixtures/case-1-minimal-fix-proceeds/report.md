<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101 — XCom.set() TypeError when value is bytes

Regression test (currently red on main):
  tests/models/test_xcom.py::TestXCom::test_serialize_bytes_value_airflow_88101
  FAILED — TypeError: Object of type bytes is not JSON serializable

Candidate area: airflow/models/xcom.py — serialize_value() at line ~139

Proposed production diff:

```diff
diff --git a/airflow/models/xcom.py b/airflow/models/xcom.py
--- a/airflow/models/xcom.py
+++ b/airflow/models/xcom.py
@@ -137,6 +137,8 @@ class XCom(Base):
     @classmethod
     def serialize_value(cls, value):
+        if isinstance(value, bytes):
+            return value
         return json.dumps(value).encode("UTF-8")
```

Targeted test run after fix:
  pytest tests/models/test_xcom.py::TestXCom::test_serialize_bytes_value_airflow_88101
  PASSED
