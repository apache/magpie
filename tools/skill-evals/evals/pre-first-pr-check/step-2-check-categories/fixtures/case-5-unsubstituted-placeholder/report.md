<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base a3b4c5d)
Commits on branch: 1
Files changed: 1 (1 added)
Diff size: 20 additions, 0 deletions

git diff --name-status output:
A       skills/my-new-skill/SKILL.md

git diff output:
--- /dev/null
+++ b/skills/my-new-skill/SKILL.md
@@ -0,0 +1,20 @@
+<!-- SPDX-License-Identifier: Apache-2.0
+     https://www.apache.org/licenses/LICENSE-2.0 -->
+---
+name: magpie-my-new-skill
+description: A skill for managing releases in <upstream>.
+license: Apache-2.0
+---
+
+# my-new-skill
+
+This skill manages the release process for <upstream>.
+
+## Step 1 — Resolve configuration
+
+Read the release configuration from <project-config>/release-trains.md.
+
+## Step 2 — Draft the release note
+
+Draft a release note for <upstream> targeting <default-branch>.
+

Commit messages:
b5c6d7e Add my-new-skill for release management

Full message for b5c6d7e:
Add my-new-skill for release management

Generated-by: Claude Code (Sonnet 4.6)
---COMMIT-END---
