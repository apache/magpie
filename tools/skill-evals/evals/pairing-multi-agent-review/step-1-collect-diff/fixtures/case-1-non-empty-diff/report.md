<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: (no arguments — use defaults)

git merge-base HEAD origin/main → a3f9c12
git diff --stat a3f9c12..HEAD:
 src/scheduler/pool.py | 14 ++++++++------
 tests/test_pool.py    |  8 ++++++++
 2 files changed, 16 insertions(+), 6 deletions(-)

git diff a3f9c12..HEAD (truncated for metadata step):
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
