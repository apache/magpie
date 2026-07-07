<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101
Title: XCom.set() raises TypeError when value is a bytes object
Reporter claimed failure: TypeError: Object of type bytes is not JSON serializable

Adapted reproducer run output:
  Command: python /tmp/reproduce_AIRFLOW-88101.py
  Exit code: 1
  stdout: (empty)
  stderr: |
    Traceback (most recent call last):
      File "/tmp/reproduce_AIRFLOW-88101.py", line 12, in <module>
        XCom.set(key="my_key", value=b"some bytes", ...)
      File "airflow/models/xcom.py", line 89, in set
        value = cls.serialize_value(value)
      File "airflow/models/xcom.py", line 142, in serialize_value
        return json.dumps(result).encode("UTF-8")
      File "/usr/lib/python3.11/json/__init__.py", line 231, in dumps
        return cls(...).encode(obj)
    TypeError: Object of type bytes is not JSON serializable
  Wall-clock: 0.8s
