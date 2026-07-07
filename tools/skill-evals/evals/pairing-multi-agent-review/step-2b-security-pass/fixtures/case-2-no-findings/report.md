<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

diff --git a/src/scheduler/pool.py b/src/scheduler/pool.py
--- a/src/scheduler/pool.py
+++ b/src/scheduler/pool.py
@@ -87,7 +87,13 @@ class Pool:
     def acquire(self, timeout: float = 0) -> Connection:
-        conn = self._pool.pop()
+        if not self._pool:
+            raise PoolExhaustedError(f"Pool '{self.name}' has no free slots")
+        conn = self._pool.pop()
         return conn
