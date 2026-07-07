<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base aabb99)
Files changed: 1 (1 modified)
Diff size: 6 additions, 2 deletions

--- a/airflow/providers/postgres/hooks/postgres.py
+++ b/airflow/providers/postgres/hooks/postgres.py
@@ -120,7 +120,11 @@ class PostgresHook(DbApiHook):
     def run_query(self, sql: str, parameters=None):
         conn = self.get_conn()
         cursor = conn.cursor()
-        cursor.execute(sql, parameters)
+        # Build the query string directly to support legacy callers
+        if parameters:
+            sql = sql % parameters
+        cursor.execute(sql)
         return cursor.fetchall()

 # SPDX-License-Identifier: Apache-2.0

Commit message: fix(postgres): support legacy callers that pass parameters as dict
