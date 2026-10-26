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

## Check 1 — Effective settings (merged scopes)

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

cat .claude/settings.local.json:
```json
{
  "sandbox": {
    "filesystem": {
      "allowRead": ["/home/alice/myrepo", "/home/alice/.cache"],
      "allowWrite": ["/home/alice/myrepo", "/home/alice/.cache"]
    }
  }
}
```

cat ~/.claude/settings.json (sandbox only):
```json
{
  "sandbox": {
    "filesystem": {"allowRead": ["/home/alice/.local/bin"]}
  }
}
```

sandbox.filesystem.denyRead in any scope: not set

uname -s: Linux (bubblewrap)

---

## Check 6 — Status-line prefix (sandbox.enabled resolution)

.claude/settings.local.json: (no sandbox.enabled key)
.claude/settings.json: sandbox.enabled = true
~/.claude/settings.local.json: (not present)
~/.claude/settings.json: (no sandbox.enabled key)

Effective sandbox.enabled: true
