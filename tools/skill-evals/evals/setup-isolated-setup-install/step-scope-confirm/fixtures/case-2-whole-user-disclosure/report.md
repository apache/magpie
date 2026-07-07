<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## User scope choice and environment state

User selection: Whole-user (with caveats)

Environment:
  OS: Ubuntu 22.04 LTS (bubblewrap + socat required)
  Framework checkout: /home/bob/magpie (verified)
  Install type: fresh
  Sync repo: ~/.claude-config (bob maintains a dotfile sync repo)

Existing settings files:
  <adopter-repo>/.claude/settings.json: not present
  ~/.claude/settings.json: present

User confirmed whole-user scope.
The skill must surface the loud disclosure (!!! WHOLE-USER SCOPE ... !!!)
and wait for explicit operator acknowledgement before writing anything.
Operator has acknowledged the disclosure and confirmed they want to proceed
with whole-user scope.
