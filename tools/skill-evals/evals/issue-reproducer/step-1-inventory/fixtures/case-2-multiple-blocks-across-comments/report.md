<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88505
Title: PythonOperator op_kwargs not passed to decorated function

Body:
  Full DAG that shows the issue:

  ```python
  from airflow import DAG
  from airflow.operators.python import PythonOperator
  from datetime import datetime

  def my_func(x, y):
      print(f"x={x}, y={y}")

  with DAG("test_dag", start_date=datetime(2024, 1, 1), schedule=None) as dag:
      PythonOperator(task_id="t1", python_callable=my_func, op_kwargs={"x": 1, "y": 2})
  ```

Comments:
  - comment-1 by reporter: "Simpler version that also fails:"

    ```python
    from airflow.operators.python import PythonOperator
    PythonOperator(task_id="t", python_callable=lambda x: print(x), op_kwargs={"x": 42}).execute({})
    ```
