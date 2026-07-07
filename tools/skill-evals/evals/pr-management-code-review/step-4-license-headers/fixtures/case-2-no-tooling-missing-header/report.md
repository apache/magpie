<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- markdownlint-disable MD030 MD037 -->
CI status-check rollup: SUCCESS
Header tooling in rollup: none

Diff summary:
  added: src/utils/StringHelper.java

--- /dev/null
+++ b/src/utils/StringHelper.java
@@ -0,0 +1,12 @@
+package org.example.utils;
+
+public class StringHelper {
+    public static String trim(String s) {
+        return s == null ? "" : s.trim();
+    }
+}
