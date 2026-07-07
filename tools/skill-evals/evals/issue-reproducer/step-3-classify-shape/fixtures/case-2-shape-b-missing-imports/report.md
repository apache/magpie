<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88202
Title: BashOperator silently ignores non-zero exit codes when append_env=True

Body:
  The following code demonstrates the issue:

  ```python
  task = BashOperator(
      task_id="fail_task",
      bash_command="exit 1",
      append_env=True,
      dag=dag,
  )
  task.execute(context={})
  ```

  This should raise AirflowException but does not.
