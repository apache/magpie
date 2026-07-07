<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## User scope choice and environment state

User selection: Per-project

Environment:
  OS: macOS
  Framework checkout: /Users/carol/magpie (verified)
  Install type: re-install (partial existing state)
  Sync repo: none

Existing settings files:
  <adopter-repo>/.claude/settings.json: PRESENT — contains existing hooks and permissions
    excerpt:
    {
      "permissions": {
        "ask": ["Bash(git push:*)"],
        "deny": ["Bash(rm -rf:*)"]
      },
      "hooks": {
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "~/.claude/scripts/sandbox-bypass-warn.sh"}]}]
      }
    }
  ~/.claude/settings.json: not present

The desired merge would add sandbox.enabled, sandbox.network, and
sandbox.filesystem blocks to the existing settings.json. The skill
must not silently overwrite the existing permissions/hooks already
present in the file.
