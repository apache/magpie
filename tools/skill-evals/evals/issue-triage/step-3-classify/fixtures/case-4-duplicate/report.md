<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-99404
Title: XCom.get_many() returns empty result when key contains special characters
Reporter: dave-contributor
Status: Open
Component: core
Filed: 2026-04-15

Body:
  When using XCom.get_many() with a key that contains characters like `|`, `:`, or `@`,
  the result is always empty even when the value was stored correctly.

  Reproduction:
  ```python
  from airflow.models import XCom
  XCom.set(key='my|key', value='test', task_id='t1', dag_id='d1', run_id='r1')
  result = XCom.get_many(key='my|key', task_ids='t1', dag_ids='d1', run_ids='r1')
  print(list(result))  # prints []
  ```

Cross-reference search results:
  - AIRFLOW-97801 (Open): "XCom key filtering broken for keys with pipe characters" — STRONG match.
    Same component, same symptom (XCom.get_many fails for special-char keys), same code path.
