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

Platform: macOS.
command -v roborev → /Users/alice/.local/bin/roborev

~/.claude/settings.json (roborev entries only):
```json
{
  "sandbox": {
    "excludedCommands": ["gh *", "roborev *"],
    "filesystem": {"allowWrite": ["~/.roborev/"]}
  },
  "permissions": {
    "ask": ["Bash(roborev *)"],
    "deny": ["Edit(**/.roborev.toml)", "Edit(~/.roborev/**)"]
  }
}
```

No permissions.allow entry in any scope matches roborev.

roborev config get server_addr --global → 127.0.0.1:7373
git rev-parse --git-path hooks → .git/hooks (no post-commit running roborev)
MCP projection: no entry with roborev: true. roborev config get mcp.enabled --global → false
