<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101
Title: XCom.set() raises TypeError when value is a bytes object

Body:
  Here is a minimal script that reproduces the issue:

  ```python
  from airflow.models import XCom, DagRun, TaskInstance
  from airflow.utils.session import create_session
  from airflow.utils.state import State
  import datetime

  with create_session() as session:
      XCom.set(
          key="my_key",
          value=b"some bytes",
          task_id="test_task",
          dag_id="test_dag",
          run_id="test_run",
          session=session,
      )
  ```

  Run with: `python reproduce.py`
  Expected: value stored successfully
  Got: `TypeError: Object of type bytes is not JSON serializable`
