<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

diff --git a/docs/contributing/setup.md b/docs/contributing/setup.md
--- a/docs/contributing/setup.md
+++ b/docs/contributing/setup.md
@@ -12,3 +12,5 @@ Run `pip install -e ".[dev]"` to install development dependencies.
+
+## Running tests
+
+Run `pytest tests/` to execute the full test suite.
+Individual modules: `pytest tests/test_scheduler.py`.
