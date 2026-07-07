<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add --output-format flag to the dags list command

Diff modifies: airflow/cli/commands/dag_command.py

--- a/airflow/cli/commands/dag_command.py
+++ b/airflow/cli/commands/dag_command.py
@@
 def dags_list(args):
+    fmt = args.output_format or "table"
     ...

Diff adds: newsfragments/45678.feature.rst

--- /dev/null
+++ b/newsfragments/45678.feature.rst
@@
+Add a ``--output-format`` flag to ``airflow dags list``.
