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
  "sandbox": {"excludedCommands": ["gh *", "roborev *"]},
  "permissions": {
    "ask": ["Bash(roborev *)"],
    "deny": ["Edit(**/.roborev.toml)", "Edit(~/.roborev/**)"]
  }
}
```

No permissions.allow entry in any scope matches roborev.
No sandbox.filesystem entry names ~/.roborev/.

git config --global --get core.hooksPath → /home/alice/.claude/git-hooks
git rev-parse --git-path hooks → /home/alice/.claude/git-hooks
cat /home/alice/.claude/git-hooks/post-commit:
  #!/bin/sh
  # roborev post-commit hook
  roborev post-commit "$@"
$(git rev-parse --git-common-dir)/hooks/post-commit → not present
test -e .roborev.toml → exit 1 (no file)

MCP projection (~/.claude.json, .mcp.json absent): no entry with roborev: true.
roborev config get mcp.enabled --global → false
