<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Check 1 (framework checkout): git fetch completed. Local checkout is up to
date with origin/main. No changes under tools/agent-isolation/,
.claude/settings.json, or docs/setup/secure-agent-setup.md.

Check 2 (pinned tools): all tools are at their pinned versions (bubblewrap
0.8.0, socat 1.7.4.4, claude-code 1.2.3). No upgrade candidates.

Check 3 (user-scope scripts): diff shows no differences between installed
scripts and framework source-of-truth.
  ~/.claude/scripts/sandbox-bypass-warn.sh — identical
  ~/.claude/scripts/sandbox-status-line.sh — identical
  ~/.claude/agent-isolation/agent-iso.sh — identical
  ~/.claude/scripts/sandbox-add-project-root.sh — identical

Check 4 (settings.json shape): no new framework entries detected.
User settings match the current framework shape.

Check 5 (re-verify): denial commands all blocked as expected.
  cat ~/.ssh/id_rsa → blocked ✓
  curl https://example.com → blocked ✓
  cat ~/.aws/credentials → blocked ✓

All checks pass. No drift detected. Setup is in sync with the framework.
