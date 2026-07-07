<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base abc1234)
Files changed: 1 (1 modified)
Diff size: 8 additions, 2 deletions

--- a/airflow/utils/dates.py
+++ b/airflow/utils/dates.py
@@ -42,7 +42,13 @@ def days_ago(n: int, hour: int = 0, ...) -> datetime:
-    return today.replace(hour=hour, minute=0, second=0, microsecond=0)
+    result = today.replace(hour=hour, minute=0, second=0, microsecond=0)
+    if n > 0:
+        result = result - timedelta(days=n)
+    elif n == 0:
+        pass  # today — no offset needed
+    else:
+        raise ValueError(f"n must be non-negative, got {n!r}")
+    return result

 # SPDX-License-Identifier: Apache-2.0
 # Existing file — header already present

Commit message: fix(dates): raise ValueError for negative n in days_ago
