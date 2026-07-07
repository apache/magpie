<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Tidy internal query builder

Diff modifies: airflow/api/_query.py

--- a/airflow/api/_query.py
+++ b/airflow/api/_query.py
@@
-def _build_query(session, dag_id):
+def _build_query(session, dag_id, *, include_subdags=False):
     ...

`_build_query` is a private helper (underscore-prefixed) used only inside
this module.
