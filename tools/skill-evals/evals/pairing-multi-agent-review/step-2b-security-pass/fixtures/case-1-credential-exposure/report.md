<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

diff --git a/src/integrations/smtp.py b/src/integrations/smtp.py
--- a/src/integrations/smtp.py
+++ b/src/integrations/smtp.py
@@ -18,6 +18,11 @@ import smtplib
+SMTP_DEFAULT_HOST = "mail.example.internal"
+SMTP_DEFAULT_PORT = 587
+_FALLBACK_PASSWORD = "hunter2"  # TODO: replace with vault lookup

 class SMTPClient:
     def __init__(self, host: str = SMTP_DEFAULT_HOST,
                  port: int = SMTP_DEFAULT_PORT,
-                 password: str | None = None) -> None:
+                 password: str = _FALLBACK_PASSWORD) -> None:
         self._host = host
