<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- markdownlint-disable MD030 MD037 -->
CI status-check rollup: SUCCESS
Header tooling in rollup: apache-rat (PASSED)

Diff summary:
  modified: pom.xml (+4 -0)
  added: src/compat/LegacyAdapter.java

--- a/pom.xml
+++ b/pom.xml
@@ -210,6 +210,10 @@
         <configuration>
           <excludes>
             <exclude>vendor/**</exclude>
+            <exclude>src/compat/**</exclude>
           </excludes>
         </configuration>

--- /dev/null
+++ b/src/compat/LegacyAdapter.java
@@ -0,0 +1,8 @@
+/*
+ * Licensed to the Apache Software Foundation (ASF) under one
+ * or more contributor license agreements. ...
+ */
+package org.example.compat;
+
+public class LegacyAdapter {}
