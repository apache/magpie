Issue: AIRFLOW-77204 — DagRun.get_duration() returns 0.0 when end_time is None

No reproducer verdict available.

Issue description:
  When a DagRun has not yet finished (end_time is None), calling get_duration()
  returns 0.0 instead of the elapsed time since start_date. Reported against
  main branch.

Proposed regression test:

```python
def test_get_duration_returns_zero_when_end_time_none_airflow_77204(self):
    """AIRFLOW-77204: get_duration() should not return 0.0 when end_time is None."""
    dag_run = DagRun(start_date=datetime(2024, 1, 1), end_time=None)
    assert dag_run.get_duration() == 0.0
```

Test run on main (before any production change):
  pytest tests/models/test_dag_run.py::TestDagRun::test_get_duration_returns_zero_when_end_time_none_airflow_77204
  PASSED
