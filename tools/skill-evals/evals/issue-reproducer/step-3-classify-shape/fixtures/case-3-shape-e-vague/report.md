<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88303
Title: Connection.get_connection_from_secrets fails with env var prefix mismatch

Body:
  When using environment variable backends, the connection lookup fails:

  ```python
  conn = Connection.get_connection_from_secrets("my_conn_id")
  ```

  Expected: returns the connection
  Got: raises KeyError
