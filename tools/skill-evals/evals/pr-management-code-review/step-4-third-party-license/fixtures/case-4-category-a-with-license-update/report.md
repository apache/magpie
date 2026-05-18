Diff adds: airflow/utils/cron_descriptor.py
Diff modifies: LICENSE
Diff adds: licenses/cron-descriptor.txt

--- /dev/null
+++ b/airflow/utils/cron_descriptor.py
@@ -0,0 +1,5 @@
+# MIT License
+# Copyright (c) 2020 Adam Schubert

+def describe(expr):
+    return expr

--- a/LICENSE
+++ b/LICENSE
@@ -310,3 +310,8 @@
+This product bundles cron-descriptor (https://github.com/Salamek/cron-descriptor),
+available under the MIT License. For details, see licenses/cron-descriptor.txt.

--- /dev/null
+++ b/licenses/cron-descriptor.txt
@@ -0,0 +1,3 @@
+MIT License
+Copyright (c) 2020 Adam Schubert
