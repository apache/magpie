<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Check 1 (framework checkout): git fetch completed. Local checkout is up to
date with origin/main.

Check 2 (pinned tools): all tools are at their pinned versions. No upgrade
candidates.

Check 3 (user-scope scripts): drift detected in 1 script.
  ~/.claude/scripts/sandbox-bypass-warn.sh — differs from framework source

  Unified diff (framework ← installed):
  --- tools/agent-isolation/sandbox-bypass-warn.sh
  +++ ~/.claude/scripts/sandbox-bypass-warn.sh
  @@ -12,7 +12,6 @@
   # Warn the user that sandbox mode is disabled.
  -echo "[magpie] WARNING: sandbox mode is disabled for this session." >&2
  +echo "[magpie] sandbox bypass active." >&2
   exit 0

  Other scripts are identical to framework source-of-truth.

Check 4 (settings.json shape): 2 new framework entries detected that are
missing from the user's .claude/settings.json:
  denyRead: /run/user/*/gnupg/
  permissions.deny: Bash(gpg:*)

Check 5 (re-verify): denial commands all blocked as expected.
  cat ~/.ssh/id_rsa → blocked ✓
  curl https://example.com → blocked ✓
  cat ~/.aws/credentials → blocked ✓
