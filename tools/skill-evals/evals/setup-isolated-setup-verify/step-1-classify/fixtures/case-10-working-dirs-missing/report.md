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

## Check 15 — Working directories under the read block

echo "$HOME/.claude/magpie" → /home/alice/.claude/magpie
echo "/tmp/claude-$(id -u)" → /tmp/claude-1000

cat ~/.claude/settings.json (permissions only):
```json
{
  "permissions": {
    "blockReadsOutsideWorkingDirectories": true,
    "additionalDirectories": ["/tmp/claude-*"]
  }
}
```

/home/alice/.claude/magpie in additionalDirectories: no
/tmp/claude-1000 in additionalDirectories: no (only the glob entry "/tmp/claude-*")
