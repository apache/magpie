<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88303
Title: Connection.get_connection_from_secrets fails with env var prefix mismatch
Reporter claimed failure: KeyError raised on connection lookup

Adapted reproducer run output:
  Command: AIRFLOW__SECRETS__BACKEND=airflow.secrets.environment_variables.EnvironmentVariablesBackend AIRFLOW_CONN_MY_CONN_ID=postgres://user:pass@host/db python /tmp/reproduce_AIRFLOW-88303.py
  Exit code: 1
  stdout: (empty)
  stderr: |
    Traceback (most recent call last):
      File "airflow/secrets/environment_variables.py", line 52, in get_conn_uri
        return os.environ[self._prefix + conn_id.upper()]
    AttributeError: 'EnvironmentVariablesBackend' object has no attribute '_prefix'
  Wall-clock: 0.3s
