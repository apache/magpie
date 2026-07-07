<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Poorani ts/ticket 36 adr document review

Body:
(PR template only; no description.)
Resolves https://github.com/break-through-19/airflow/issues/36

Commits (all by the listed authors, opened by single account break-through-19):
- 09:01 break-through-19  "Merge pull request #12 from break-through-19/adr"
- 09:14 break-through-19  "Merge pull request #13 from break-through-19/ui"
- 09:31 break-through-19  "Merge pull request #14 from break-through-19/sdk"
- 09:33 sanwar47          "sprint 3 board cleanup"
- 09:35 sharan-s2k        "CSS 566A team submission"

Changed files (gh pr view --json files — path/additions/deletions only):
- team_project/README.md
- team_project/main.py
- go-sdk/client.go
- airflow-core/ui/panel.tsx
- docs/adr/0001.md
- scripts/run_demo.sh

Unified diff (gh pr diff, excerpt):
diff --git a/team_project/README.md b/team_project/README.md
new file mode 100644
index 0000000..a1b2c3d
--- /dev/null
+++ b/team_project/README.md
@@ -0,0 +1,2 @@
+# CSS 566A - Software Management, University of Washington Bothell
+Team class project.
diff --git a/team_project/main.py b/team_project/main.py
new file mode 100644
index 0000000..d4e5f6a
--- /dev/null
+++ b/team_project/main.py
@@ -0,0 +1,3 @@
+def main():
+    print("team project")

Labels: area:UI, area:task-sdk, area:go-sdk

CI status checks: Mergeable (bot), WIP (bot). No project CI workflows ran.
