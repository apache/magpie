<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tool: mypy
Confirmed findings (user selected all):

mypy:ANN201:airflow/api/common/mark_tasks.py:47 — Missing return type annotation for public function `mark_task_instance_state`
mypy:ANN001:airflow/api/common/mark_tasks.py:48 — Missing type annotation for function argument `task_id`
mypy:ANN001:airflow/api/common/mark_tasks.py:49 — Missing type annotation for function argument `dag_id`
mypy:ANN201:airflow/utils/dag_cycle_tester.py:23 — Missing return type annotation for public function `check_cycle`

No security labels present.
