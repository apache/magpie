<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101 — XCom.set() TypeError when value is bytes

Reproducer verdict:
  Confirmed: yes
  Reproduction: XCom.serialize_value(b"hello") raises TypeError: Object of type bytes
  is not JSON serializable
  No existing test covers the bytes input path.

Proposed regression test:

```python
def test_serialize_bytes_value_airflow_88101(self):
    """AIRFLOW-88101: bytes values must pass through without JSON serialization."""
    result = XCom.serialize_value(b"hello")
    assert result == b"hello"
```

Test run on main (before any production change):
  pytest tests/models/test_xcom.py::TestXCom::test_serialize_bytes_value_airflow_88101
  FAILED — TypeError: Object of type bytes is not JSON serializable
