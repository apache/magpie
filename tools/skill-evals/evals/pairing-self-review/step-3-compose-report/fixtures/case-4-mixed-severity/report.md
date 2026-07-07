<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base 9a2b3c4)
Files changed: 2 (1 added, 1 modified)
Diff size: 14 additions, 2 deletions

Classified findings:
  correctness:
    - blocking | airflow/providers/mysql/hooks/mysql.py:66-72
      summary: cursor unbound on the MySQLError path; the unconditional return cursor.fetchall() raises NameError when get_conn fails
      evidence: "+        except MySQLError as e:\n+            self.log.error(\"Query failed: %s\", e)\n+        return cursor.fetchall()"
  security: no findings
  conventions:
    - advisory | airflow/providers/mysql/utils.py:1
      summary: new file missing the SPDX license header
      evidence: "+def normalise_table_name(name: str) -> str:"
    - advisory | airflow/providers/mysql/hooks/mysql.py:62
      summary: narrating comment restates the code on the next line; drop it
      evidence: "+        # Build the query for the requested table"
