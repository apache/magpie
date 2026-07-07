<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-99707
Title: KeyError in BashOperator when env dict has integer values
Reporter claimed failure: KeyError when env values are integers

Adapted reproducer run output:
  Command: python /tmp/reproduce_AIRFLOW-99707.py
  Exit code: 1
  stdout: (empty)
  stderr: |
    Traceback (most recent call last):
      File "airflow/operators/bash.py", line 211, in execute
        result = self.subprocess_hook.run_command(
      File "airflow/utils/process_utils.py", line 121, in run_command
        proc = subprocess.Popen(cmd, env=env, ...)
    TypeError: env: key must be a str, not int (actually the value was int, not the key)
  Wall-clock: 0.4s

  Relevant documentation check:
  https://airflow.apache.org/docs/apache-airflow/stable/howto/operator/bash.html states:
  "env (dict | None) – If set, overrides the environment variables ... All values must be strings."
  subprocess.Popen documentation confirms: env dict must contain only string values.
