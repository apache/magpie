<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Category being checked: Third-party license compliance

Diff excerpt:
```diff
diff --git a/requirements.txt b/requirements.txt
index 4a2c8f1..9b3d7e2 100644
--- a/requirements.txt
+++ b/requirements.txt
@@ -14,6 +14,7 @@ apache-airflow-providers-http>=4.0.0
 arrow>=1.2.3
 attrs>=22.2.0
 blinker>=1.6.2
+gplv2-utility-lib>=1.3.0
 humanize>=4.6.0
 importlib-metadata>=6.0.0
```

The newly added dependency `gplv2-utility-lib` is licensed under GPL v2. The Apache Software Foundation's third-party licensing policy classifies GPL as Category X, which means it cannot be included in an ASF release in any form.
