<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: staged

git diff --cached --stat:
 src/auth/tokens.py | 5 +++++
 1 file changed, 5 insertions(+)

git diff --cached (truncated for metadata step):
diff --git a/src/auth/tokens.py b/src/auth/tokens.py
--- a/src/auth/tokens.py
+++ b/src/auth/tokens.py
@@ -42,0 +43,5 @@ class TokenStore:
+    def rotate(self, token_id: str) -> str:
+        """Rotate an existing token, invalidating the old one."""
+        old = self._tokens.pop(token_id, None)
+        new_token = secrets.token_hex(32)
+        self._tokens[new_token] = old.owner if old else None
+        return new_token
