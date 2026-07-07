<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Hand-back: mypy findings — airflow/api/common/

**Tool:** mypy — 3 findings addressed, 1 suppressed

**Branch:** fix/audit-mypy-api-annotations
**Commit:** 7a1bc34

**Verify command:** `mypy airflow/api/common/mark_tasks.py airflow/api/common/delete_dag.py`
**Result:** 0 errors — all findings cleared or suppressed

**Diff scope:**
- `airflow/api/common/mark_tasks.py` — added `-> None` return annotation (ANN201); added `str` argument annotations (ANN001 ×2)
- `airflow/api/common/delete_dag.py` — added `# type: ignore[return]` suppression on line 77

**Suppressed findings:**
- `mypy:ANN201:airflow/api/common/delete_dag.py:77` — user confirmed this is a false positive caused by a third-party library stub returning `Any`; suppressed with `# type: ignore[return]` per user instruction.

**Open questions:** The suppressed finding in `delete_dag.py` may clear once the `apache-airflow-stubs` package is updated. Maintainer should revisit when stubs are bumped.
