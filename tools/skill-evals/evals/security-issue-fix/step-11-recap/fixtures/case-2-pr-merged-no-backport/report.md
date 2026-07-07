<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Apply result

**PR opened:** https://github.com/apache/airflow/pull/65703
**Branch:** `fix-http-operator-redirect-validation` (in fork `justinpakzad/airflow`)
**Tracker:** https://github.com/airflow-s/airflow-s/issues/341

**Files changed:**
- `airflow/providers/http/operators/http.py` — added `allow_redirects=False` default with configurable override

**Test results:**
- `uv run --project airflow-core pytest tests/providers/http/operators/test_http.py::TestHttpOperator::test_redirect_blocked -xvs` → PASSED (1 test)
- `prek run --from-ref main --stage pre-commit` → PASSED

**Tracker comment posted:** https://github.com/airflow-s/airflow-s/issues/341#issuecomment-9080

**Backport label:** None needed — milestone is Airflow 3.3.0 (next main-branch release).

Produce the recap.
