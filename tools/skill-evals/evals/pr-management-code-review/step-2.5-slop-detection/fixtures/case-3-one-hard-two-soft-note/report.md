<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add experiments package

Body:
(PR template only; no description.)

Commits (opened by single account dev-maria, authored by dev-maria):
- 11:00 dev-maria  "add experiments scaffold"

Changed files (gh pr view --json files — path/additions/deletions only):
- experiments/pyproject.toml
- experiments/sandbox.py

Unified diff (gh pr diff, excerpt):
diff --git a/experiments/pyproject.toml b/experiments/pyproject.toml
new file mode 100644
index 0000000..b7c8d9e
--- /dev/null
+++ b/experiments/pyproject.toml
@@ -0,0 +1,3 @@
+[project]
+name = "experiments"
+description = "a personal playground project"
diff --git a/experiments/sandbox.py b/experiments/sandbox.py
new file mode 100644
index 0000000..e1f2a3b
--- /dev/null
+++ b/experiments/sandbox.py
@@ -0,0 +1,2 @@
+# personal playground
+print("scratch")

Labels: area:core

CI status checks: Mergeable (bot) only. No project CI workflows ran.
