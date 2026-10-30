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
    "filesystem": {"denyRead": ["~/"], "allowRead": ["."], "allowWrite": ["."]}
  },
  "permissions": {
    "deny": ["Read(~/.aws/**)", "Bash(curl *)"],
    "ask": ["Bash(gh pr create *)"]
  }
}
```

---

## Check 16 — Read-only vetted ops never prompt

The repo uses the vetted-ops dispatcher (.apache-magpie-overrides/tools/vetted-ops/config.toml exists).

echo "$HOME/.claude/magpie" → /home/alice/.claude/magpie

cat /home/alice/myrepo/.claude/settings.local.json (permissions only):
```json
{
  "permissions": {
    "additionalDirectories": ["/home/alice/.claude/magpie", "/tmp/claude-1000"]
  }
}
```

16a both allow rules: present in .claude/settings.json
16b no ask rule matches vetted-op-read: none found
16c blockReadsOutsideWorkingDirectories: absent in every scope
16d tamper-protection Edit denies: all three present
16e exclusions for both launchers: present
16f working directory overlapping /home/alice/.claude/magpie: "/home/alice/.claude/magpie" in .claude/settings.local.json additionalDirectories
