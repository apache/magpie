**REQUEST_CHANGES**

- [major] airflow/api/client.py: removing the public `schedule` parameter
  breaks existing callers; keep it through a deprecation cycle.
- [minor] airflow/api/client.py: add a test for the new behaviour.

(End of review body — no footer follows.)
