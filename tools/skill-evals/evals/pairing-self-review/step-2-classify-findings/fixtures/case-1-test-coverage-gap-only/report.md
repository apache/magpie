<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base abc1234)
Files changed: 1 (1 modified; existing file, SPDX header unchanged)
Diff size: 2 additions, 0 deletions

--- a/airflow/utils/dates.py
+++ b/airflow/utils/dates.py
@@ -38,4 +38,6 @@ from datetime import datetime, timedelta, timezone
 def days_ago(n: int, hour: int = 0) -> datetime:
     """Return midnight (plus ``hour``) ``n`` days before today. ``n`` must be non-negative."""
+    if n < 0:
+        raise ValueError(f"n must be non-negative, got {n!r}")
     today = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0)
     return today - timedelta(days=n)

Commit message: fix(dates): enforce the documented non-negative n in days_ago
