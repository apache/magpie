<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Parse the config payload

Diff adds: airflow/utils/config_loader.py

--- /dev/null
+++ b/airflow/utils/config_loader.py
@@
+import json
+
+def load_config(raw: str) -> dict:
+    # parse the JSON config
+    return json.parse(raw)
