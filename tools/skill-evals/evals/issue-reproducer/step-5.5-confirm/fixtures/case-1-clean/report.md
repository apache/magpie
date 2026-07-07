<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101 — XCom.set() TypeError
Reporter: alice-dev

Adapted reproducer:
  from airflow.models import XCom
  from airflow.utils.session import create_session

  with create_session() as session:
      XCom.set(key="k", value=b"bytes", task_id="t", dag_id="d", run_id="r", session=session)
