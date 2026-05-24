Issue: AIRFLOW-88101 — XCom.set() TypeError when value is bytes

Reproducer verdict:
  Confirmed: yes
  Reproduction: XCom.serialize_value(b"hello") raises TypeError: Object of type bytes
  is not JSON serializable
  No existing test covers the bytes input path.

Proposed regression test:

```python
def test_serialize_bytes_passthrough(self):
    result = XCom.serialize_value(b"hello")
    assert result == b"hello"
```

Test run on main (before any production change):
  pytest tests/models/test_xcom.py::TestXCom::test_serialize_bytes_passthrough
  FAILED — TypeError: Object of type bytes is not JSON serializable
