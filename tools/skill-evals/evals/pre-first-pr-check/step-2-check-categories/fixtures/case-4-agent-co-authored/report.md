<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base f9a1b2c)
Commits on branch: 1
Files changed: 1 (1 modified)
Diff size: 5 additions, 2 deletions

git diff --name-status output:
M       docs/setup/README.md

git diff output:
--- a/docs/setup/README.md
+++ b/docs/setup/README.md
@@ -10,7 +10,10 @@ ## Prerequisites
-Before installing, ensure you have Python 3.10+ and `uv` installed.
+Before installing, ensure you have:
+
+- Python 3.10 or later
+- `uv` (install via `pip install uv` or your package manager)
+- `prek` (install via `pip install prek`)

Commit messages:
efa4567 Expand setup prerequisites list

Full message for efa4567:
Expand setup prerequisites list

Break the prerequisites line into a bullet list and add prek.

Co-Authored-By: Claude <noreply@anthropic.com>
---COMMIT-END---
