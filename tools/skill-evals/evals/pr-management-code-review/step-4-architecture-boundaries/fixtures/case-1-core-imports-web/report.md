<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Render dag summary in scheduler

Diff modifies: airflow/core/scheduler.py

--- a/airflow/core/scheduler.py
+++ b/airflow/core/scheduler.py
@@
+from airflow.www.views import render_dag_summary
+
 class Scheduler:
     def _log_summary(self, dag):
-        log.info("scheduling %s", dag.dag_id)
+        log.info(render_dag_summary(dag))
