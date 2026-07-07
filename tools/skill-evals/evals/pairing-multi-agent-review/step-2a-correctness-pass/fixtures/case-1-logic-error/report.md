<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

diff --git a/src/scheduler/pool.py b/src/scheduler/pool.py
--- a/src/scheduler/pool.py
+++ b/src/scheduler/pool.py
@@ -92,7 +92,7 @@ class Pool:
     def release(self, conn: Connection) -> None:
-        self._pool.append(conn)
+        self._pool.insert(0, conn)
         self._waiters.notify_all()

@@ -101,6 +101,9 @@ class Pool:
     def acquire_many(self, n: int, timeout: float = 0) -> list[Connection]:
+        if n <= 0:
+            return []
         results = []
         for _ in range(n):
             results.append(self.acquire(timeout=timeout))
+        return results
-        return results if len(results) == n else []
