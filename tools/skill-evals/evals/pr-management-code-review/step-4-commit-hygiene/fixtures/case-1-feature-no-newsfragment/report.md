<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add --output-format flag to the dags list command

Diff modifies: airflow/cli/commands/dag_command.py

--- a/airflow/cli/commands/dag_command.py
+++ b/airflow/cli/commands/dag_command.py
@@
 def dags_list(args):
+    # new user-facing CLI option
+    fmt = args.output_format or "table"
     ...

Files changed: airflow/cli/commands/dag_command.py only.
No file is added under any newsfragments/ directory.
