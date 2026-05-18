CI status-check rollup: SUCCESS
Header tooling in rollup: license-eye (PASSED)
Exclusion config changes in this diff: none

Diff summary:
  added: src/util/Parser.py

--- /dev/null
+++ b/src/util/Parser.py
@@ -0,0 +1,10 @@
+# SPDX-License-Identifier: MIT
+#
+# Utility parser for internal use.
+
+def parse(s):
+    return s.strip().split(",")
