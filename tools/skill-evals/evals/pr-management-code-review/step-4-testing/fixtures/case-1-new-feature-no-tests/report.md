<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add slugify helper for dag ids

Diff adds: airflow/utils/slugify.py

--- /dev/null
+++ b/airflow/utils/slugify.py
@@
+def slugify(value: str) -> str:
+    """Return a URL-safe slug for the given value."""
+    return "-".join(value.lower().split())

No test files are added or modified in this PR.
