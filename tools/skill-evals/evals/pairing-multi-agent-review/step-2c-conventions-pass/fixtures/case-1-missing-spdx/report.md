<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

diff --git a/src/notifications/webhook.py b/src/notifications/webhook.py
new file mode 100644
--- /dev/null
+++ b/src/notifications/webhook.py
@@ -0,0 +1,18 @@
+"""Webhook notification dispatcher."""
+import json
+import urllib.request
+
+
+class WebhookDispatcher:
+    def __init__(self, url: str) -> None:
+        self._url = url
+
+    def dispatch(self, payload: dict) -> None:
+        data = json.dumps(payload).encode()
+        req = urllib.request.Request(
+            self._url, data=data,
+            headers={"Content-Type": "application/json"},
+            method="POST",
+        )
+        with urllib.request.urlopen(req) as _resp:
+            pass
