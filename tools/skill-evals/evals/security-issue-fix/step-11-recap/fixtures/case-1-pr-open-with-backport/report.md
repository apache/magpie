<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Apply result

**PR opened:** https://github.com/apache/airflow/pull/52199
**Branch:** `fix-xcom-deserialize-type-check` (in fork `contributor-x/airflow`)
**Tracker:** https://github.com/airflow-s/airflow-s/issues/312

**Files changed:**
- `airflow/models/xcom.py` — replaced `pickle.loads()` with `json.loads()` in `deserialize_value()`
- `tests/models/test_xcom.py` — added `test_xcom_deserialize_rejects_pickle` test case

**Test results:**
- `uv run --project airflow-core pytest tests/models/test_xcom.py -xvs` → PASSED (3 tests)
- `prek run --from-ref main --stage pre-commit` → PASSED
- `uv run --project airflow-core --with "apache-airflow-devel-common[mypy]" mypy airflow/models/xcom.py` → PASSED

**Tracker comment posted:** https://github.com/airflow-s/airflow-s/issues/312#issuecomment-9055

**Backport label applied:** `backport-to-v3-2-test`

Produce the recap.
