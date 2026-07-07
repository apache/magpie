<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Hand-back: AIRFLOW-88101

**Issue:** AIRFLOW-88101 — XCom.set() TypeError when value is bytes

**Branch:** fix/AIRFLOW-88101-xcom-bytes
**Commit:** abc1234

**Targeted test:** `pytest tests/models/test_xcom.py::TestXCom::test_serialize_bytes_value` — PASSED

**Module test:** `pytest tests/models/test_xcom.py` — 42 passed, 0 failed

**Diff scope:** 1 file changed (airflow/models/xcom.py — added bytes early-return), 1 test file added.

**Open questions:** None — fix is straightforward. Maintainer should verify whether the bytes path should also handle bytearray.
