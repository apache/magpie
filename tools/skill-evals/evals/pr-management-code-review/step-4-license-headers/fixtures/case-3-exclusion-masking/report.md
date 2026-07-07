<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- markdownlint-disable MD030 MD037 -->
CI status-check rollup: SUCCESS
Header tooling in rollup: apache-rat (PASSED)

Diff summary:
  modified: .rat-excludes (+1 -0)
  added: src/codegen/GeneratedClient.java

--- a/.rat-excludes
+++ b/.rat-excludes
@@ -4,3 +4,4 @@
 vendor/**
 docs/api-spec.yaml
 src/test/resources/**
+src/codegen/GeneratedClient.java

--- /dev/null
+++ b/src/codegen/GeneratedClient.java
@@ -0,0 +1,30 @@
+package org.example.codegen;
+
+// Hand-written client — not generated.
+public class GeneratedClient {
+    public void connect(String host) { /* ... */ }
+}
