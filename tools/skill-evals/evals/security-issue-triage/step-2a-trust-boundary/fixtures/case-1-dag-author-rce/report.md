<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Reporter claims: A DAG author can write a DAG that passes a value read
from an Airflow Variable directly to BashOperator's bash_command argument.
If the Variable value contains shell metacharacters, arbitrary shell
commands execute on the worker host under the airflow user.

Attacker: DAG author (has write access to DAGs and Variables in the
  deployment)
Component: BashOperator, Airflow worker process
Effect: arbitrary shell command execution on the worker host
