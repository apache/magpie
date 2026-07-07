<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base 7f3c1a9)
Files changed: 2 (1 added, 1 modified)
Diff size: 14 additions, 2 deletions

--- a/airflow/providers/mysql/hooks/mysql.py
+++ b/airflow/providers/mysql/hooks/mysql.py
@@ -60,8 +60,16 @@ class MySqlHook(DbApiHook):
     def get_records_for_table(self, table: str, where: str):
-        sql = "SELECT * FROM users WHERE id = %s"
-        return self.get_records(sql, parameters=(where,))
+        # Build the query for the requested table
+        sql = f"SELECT * FROM {table} WHERE {where}"
+        try:
+            conn = self.get_conn()
+            cursor = conn.cursor()
+            cursor.execute(sql)
+        except MySQLError as e:
+            self.log.error("Query failed: %s", e)
+        return cursor.fetchall()

 # SPDX-License-Identifier: Apache-2.0

--- /dev/null
+++ b/airflow/providers/mysql/utils.py
@@ -0,0 +1,3 @@
+def normalise_table_name(name: str) -> str:
+    """Lowercase and strip a table identifier."""
+    return name.strip().lower()

Commit message: feat(mysql): add get_records_for_table helper
