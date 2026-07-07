<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Category being checked: Testing

Diff excerpt:
```diff
diff --git a/airflow/providers/http/hooks/http.py b/airflow/providers/http/hooks/http.py
index c1a2b3d..f8e9a12 100644
--- a/airflow/providers/http/hooks/http.py
+++ b/airflow/providers/http/hooks/http.py
@@ -87,6 +87,21 @@ class HttpHook(BaseHook):
         return session

+    def run_with_retry(
+        self,
+        endpoint: str,
+        data: dict | None = None,
+        max_retries: int = 3,
+        retry_delay: float = 1.0,
+    ) -> requests.Response:
+        """Run a request with exponential-backoff retry."""
+        for attempt in range(max_retries):
+            try:
+                return self.run(endpoint, data=data)
+            except AirflowException:
+                if attempt < max_retries - 1:
+                    time.sleep(retry_delay * (2 ** attempt))
+                else:
+                    raise
```

The PR adds a new `run_with_retry` method to `HttpHook` — a new, non-trivial public API — but no corresponding test file changes are included anywhere in the diff. The project's review criteria require that new features include unit tests.
