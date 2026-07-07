<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add team project

Body:
(PR template only; no description.)

statusCheckRollup: Mergeable (bot), WIP (bot)  — no project CI workflows ran.

commits (opened by single account break-through-19, all authored by break-through-19):
- 09:01  "Merge pull request #12 from break-through-19/adr"
- 09:18  "Merge pull request #13 from break-through-19/ui"
- 09:33  "Merge pull request #14 from break-through-19/sdk"

files (exactly as `gh pr view --json files` returns — path/additions/deletions only, no changeType):
- { "path": "team_project/README.md", "additions": 40, "deletions": 0 }
- { "path": "team_project/main.py",   "additions": 120, "deletions": 0 }

Unified diff (gh pr diff — added-ness is only visible here, not in --json files):
diff --git a/team_project/README.md b/team_project/README.md
new file mode 100644
index 0000000..c0ffee1
--- /dev/null
+++ b/team_project/README.md
@@ -0,0 +1,2 @@
+# CS101 class project — Intro to Software, Fall 2025
+Team submission.
diff --git a/team_project/main.py b/team_project/main.py
new file mode 100644
index 0000000..0badf00
--- /dev/null
+++ b/team_project/main.py
@@ -0,0 +1,3 @@
+def main():
+    print("hello")
