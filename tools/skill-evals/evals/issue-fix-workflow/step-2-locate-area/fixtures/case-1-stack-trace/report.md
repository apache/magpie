<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101 — XCom.set() TypeError with bytes
No maintainer pointer in comments.

Reproducer verdict stack trace:
  File "airflow/models/xcom.py", line 89, in set
    value = cls.serialize_value(value)
  File "airflow/models/xcom.py", line 142, in serialize_value
    return json.dumps(result).encode("UTF-8")
  TypeError: Object of type bytes is not JSON serializable
