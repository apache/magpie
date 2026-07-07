<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Fix plan context

**File changed:** `airflow/models/xcom.py`
**Change:** Replace `pickle.loads(value)` with `json.loads(value)` in `deserialize_value()` at line 312.

**Existing test file:** `tests/models/test_xcom.py`
- `TestXCom::test_xcom_deserialize_value` — exercises the deserialization path with valid JSON payloads.
- `TestXCom::test_xcom_push_pull` — end-to-end push/pull round-trip.

**New tests required:** Yes — the existing tests only cover valid JSON. A new test must assert that a legacy pickle payload now raises `json.JSONDecodeError` rather than silently deserializing.

**Type-check applicable:** Yes — `deserialize_value` has a return type annotation.

Produce the test plan for step 4d.
