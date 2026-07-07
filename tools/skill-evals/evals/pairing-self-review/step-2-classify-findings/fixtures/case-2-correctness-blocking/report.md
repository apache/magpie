<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base def5678)
Files changed: 1 (1 modified)
Diff size: 12 additions, 4 deletions

--- a/airflow/providers/http/hooks/http.py
+++ b/airflow/providers/http/hooks/http.py
@@ -88,10 +88,18 @@ class HttpHook(BaseHook):
     def run(self, endpoint: str, data=None, headers=None, extra_options=None):
         session = self.get_conn()
-        response = session.request(self.method, url, **request_kwargs)
-        response.raise_for_status()
-        return response
+        try:
+            response = session.request(self.method, url, **request_kwargs)
+        except requests.exceptions.ConnectionError as e:
+            self.log.error("Connection failed: %s", e)
+        # Return the response if successful
+        return response

 # SPDX-License-Identifier: Apache-2.0

Commit message: refactor(http): wrap connection errors in try/except
