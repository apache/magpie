<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

fix(api): add missing type annotations in mark_tasks.py and dag_cycle_tester.py

Mypy reported four missing annotations (ANN001, ANN201). Added
return type `-> None` to `mark_task_instance_state` and
`check_cycle`, and `str` parameter annotations for `task_id` and
`dag_id`. Types inferred from call sites and existing docstrings.
