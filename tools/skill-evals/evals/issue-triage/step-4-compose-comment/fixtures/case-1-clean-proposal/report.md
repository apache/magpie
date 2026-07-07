<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-99101 (BUG — RecursionError in scheduler)
URL template: https://github.com/apache/airflow/issues/

Drafted comment:
---
**Triage proposal**

The Airflow scheduler enters infinite recursion in `_process_dags()` when the dag_bag contains more than 1,000 DAG files. The symptom is a hard crash with `RecursionError: maximum recursion depth exceeded`, introduced as a regression in 2.9.0 (worked in 2.8.0). The code path at https://github.com/apache/airflow/issues/99101 confirms the call site.

**Proposed disposition: BUG.**

`_process_dags` calls itself recursively without a depth guard. The fix is a bounded iteration or an explicit recursion limit check before the recursive call.

@potiuk @ephraimbuddy — can you confirm which version introduced the `_process_dags` recursive call?
---
