<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Check results (all 8 checks ran):

  Check 1 (project settings.json): ✗  sandbox.enabled: false
  Check 2 (user-scope hooks):       ✗  PreToolUse hook missing; no statusLine entry
  Check 3 (hook scripts):           ✗  ~/.claude/scripts/ does not exist
  Check 4 (claude-iso):             ✗  source line missing from shell rc
  Check 5 (pinned versions):        ⚠  claude-code 1.9.0 installed, pin is 2.1.150 (older than pin)
  Check 6 (sandbox.enabled):        ✗  effective sandbox.enabled: false
  Check 7 (denial commands):        ✗  cat ~/.aws/credentials: readable; curl: succeeded
  Check 8 (project root):           ✗  .claude/settings.local.json absent; live probe failed

sandbox-add-project-root.sh helper installed: no
Snapshot drift: none
