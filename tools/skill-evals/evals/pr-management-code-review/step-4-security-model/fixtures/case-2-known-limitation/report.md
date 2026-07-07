<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add a python_callable shortcut to the custom operator

Diff modifies: airflow/providers/custom/operators/run.py

--- a/airflow/providers/custom/operators/run.py
+++ b/airflow/providers/custom/operators/run.py
@@
 class RunOperator(BaseOperator):
-    def __init__(self, command, **kwargs):
+    def __init__(self, command=None, python_callable=None, **kwargs):
         super().__init__(**kwargs)
+        self.python_callable = python_callable
     def execute(self, context):
-        run_shell(self.command)
+        if self.python_callable:
+            return self.python_callable(context)
+        run_shell(self.command)

This lets a DAG author pass arbitrary Python to execute on the worker.
