<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Fix off-by-one in retry-window calculation

Diff modifies: airflow/models/taskinstance.py

--- a/airflow/models/taskinstance.py
+++ b/airflow/models/taskinstance.py
@@
 def remaining_retries(self):
-    return self.max_tries - self.try_number
+    return self.max_tries - self.try_number + 1

No test files are added or modified in this PR.
