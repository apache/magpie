<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Snapshot drift check

cat .apache-magpie.lock:
  method: git-branch
  url: https://github.com/apache/magpie.git
  ref: v0.9.1

cat .apache-magpie.local.lock:
  method: git-branch
  url: https://github.com/apache/magpie.git
  ref: v0.9.1

Result: lock files match — no drift.

---

## Check 1 — Project .claude/settings.json

cat .claude/settings.json:
```json
{
  "sandbox": {
    "enabled": true,
    "network": {"allowedDomains": ["github.com", "api.github.com", "pypi.org"]},
    "filesystem": {"allowRead": ["."], "allowWrite": ["."]}
  },
  "permissions": {
    "deny": ["Read(~/.aws/**)", "Bash(curl *)"],
    "ask": ["Bash(gh pr create *)"]
  }
}
```

---

## Check 17 — roborev exclusion, if installed

command -v roborev → /home/alice/.local/bin/roborev

~/.claude/settings.json (roborev entries only):
```json
{
  "sandbox": {
    "excludedCommands": ["gh *", "roborev *"]
  },
  "permissions": {
    "allow": [
      "Bash(roborev version*)",
      "Bash(roborev status*)",
      "Bash(roborev review *)",
      "Bash(roborev show *)"
    ],
    "ask": [
      "Bash(roborev fix *)",
      "Bash(roborev refine *)",
      "Bash(roborev run *)"
    ]
  }
}
```

Project .claude/settings.json and settings.local.json: no roborev entries.
No sandbox.filesystem.allowRead or allowWrite entry in any scope names ~/.roborev/.
