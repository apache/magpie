<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base cc1122)
Files changed: 2 (1 added, 1 modified)
Diff size: 35 additions, 0 deletions

--- /dev/null
+++ b/airflow/utils/string_utils.py
@@ -0,0 +1,20 @@
+def truncate(value: str, max_len: int = 100) -> str:
+    """Truncate a string to max_len characters, appending '...' if truncated."""
+    if len(value) <= max_len:
+        return value
+    return value[: max_len - 3] + "..."
+
+def pad_left(value: str, width: int, char: str = " ") -> str:
+    """Left-pad a string to width using char."""
+    return value.rjust(width, char)

--- a/airflow/utils/__init__.py
+++ b/airflow/utils/__init__.py
@@ -1,3 +1,4 @@
 # Licensed to the Apache Software Foundation (ASF) under one
+from airflow.utils.string_utils import truncate, pad_left

Commit message: feat(utils): add string_utils helpers
