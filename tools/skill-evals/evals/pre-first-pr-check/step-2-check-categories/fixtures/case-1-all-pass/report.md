<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base f1a2b3c)
Commits on branch: 1
Files changed: 1 (1 added)
Diff size: 12 additions, 0 deletions

git diff --name-status output:
A       docs/setup/quick-start.md

git diff output:
--- /dev/null
+++ b/docs/setup/quick-start.md
@@ -0,0 +1,12 @@
+<!-- SPDX-License-Identifier: Apache-2.0
+     https://www.apache.org/licenses/LICENSE-2.0 -->
+
+# Quick-start guide
+
+1. Clone the repository.
+2. Run `prek install` to install the pre-commit hook.
+3. Copy `projects/_template/` to your project-config directory.
+4. Edit the `project.md` in your project-config directory with your project identity.
+5. Run `/magpie-setup verify` to confirm the setup is complete.
+
+See [install-recipes.md](install-recipes.md) for full options.

Commit messages:
abc1234 Add quick-start guide to setup docs

Full message for abc1234:
Add quick-start guide to setup docs

A concise guide covering the five steps to get a new adopter
running, bridging the gap between the README and install-recipes.md.

Generated-by: Claude Code (Sonnet 4.6)
---COMMIT-END---
