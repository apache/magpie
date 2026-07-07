<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

File: scripts/sync.sh
Status: M (modified)
User confirmation: "yes, commit this"

Diff:
--- a/scripts/sync.sh
+++ b/scripts/sync.sh
@@ -10,7 +10,7 @@
 set -euo pipefail

 # Wait this long (seconds) between automated pulls to avoid hammering the remote.
-COOLDOWN=300
+COOLDOWN=600

 # Pull latest config from the sync repo.
 flock --nonblock ~/.claude-config/.sync.lock \
