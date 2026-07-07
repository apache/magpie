<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base d4e5f6a)
Commits on branch: 1
Files changed: 1 (1 added)
Diff size: 8 additions, 0 deletions

git diff --name-status output:
A       tools/my-helper/helper.py

git diff output:
--- /dev/null
+++ b/tools/my-helper/helper.py
@@ -0,0 +1,8 @@
+"""Helper utilities for the my-helper tool."""
+
+
+def compute_hash(data: str) -> str:
+    """Return a SHA-256 hex digest of data."""
+    import hashlib
+    return hashlib.sha256(data.encode()).hexdigest()
+

Commit messages:
bcd2345 Add helper utility for hashing

Full message for bcd2345:
Add helper utility for hashing

Implements a simple SHA-256 wrapper used by the my-helper tool.

Generated-by: Claude Code (Sonnet 4.6)
---COMMIT-END---
