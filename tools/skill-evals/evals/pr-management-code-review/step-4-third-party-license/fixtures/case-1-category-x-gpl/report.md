Diff adds: vendor/slugify/slugify.py

--- /dev/null
+++ b/vendor/slugify/slugify.py
@@ -0,0 +1,6 @@
+# SPDX-License-Identifier: GPL-2.0-only
+# Copyright (C) 2019 Example Corp.
+
+def slugify(s):
+    return s.lower().replace(" ", "-")

LICENSE file modified in this PR: no
