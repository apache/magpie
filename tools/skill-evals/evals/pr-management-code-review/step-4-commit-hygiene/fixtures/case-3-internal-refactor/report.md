<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Rename internal helper _fmt to _format_row

Diff modifies: airflow/cli/commands/dag_command.py

--- a/airflow/cli/commands/dag_command.py
+++ b/airflow/cli/commands/dag_command.py
@@
-def _fmt(row):
+def _format_row(row):
     return " ".join(str(c) for c in row)

Pure internal rename with no change to behaviour or output.
No newsfragment is added.
