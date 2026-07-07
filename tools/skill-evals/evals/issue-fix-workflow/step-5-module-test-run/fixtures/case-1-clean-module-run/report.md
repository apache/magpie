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
  test_xcom.py::TestXCom::test_clear_removes_value PASSED

  7 passed, 0 failed in 0.43s
