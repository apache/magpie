<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Fix applied: AIRFLOW-88101 — bytes early-return in XCom.serialize_value()

Module test run:
  pytest tests/models/test_xcom.py

  test_xcom.py::TestXCom::test_serialize_value_string PASSED
  test_xcom.py::TestXCom::test_serialize_value_int PASSED
  test_xcom.py::TestXCom::test_serialize_value_dict PASSED
  test_xcom.py::TestXCom::test_serialize_value_none PASSED
  test_xcom.py::TestXCom::test_serialize_bytes_value_airflow_88101 PASSED
  test_xcom.py::TestXCom::test_set_and_get_value PASSED
  test_xcom.py::TestXCom::test_round_trip_bytes_via_set FAILED

  FAILED test_xcom.py::TestXCom::test_round_trip_bytes_via_set
  AssertionError: assert b'hello' == 'hello'
  XCom.get() deserializes the stored value with json.loads().decode(), but
  the bytes early-return skips encoding, so the round-trip no longer matches
  the expected string output.

  6 passed, 1 failed in 0.45s
