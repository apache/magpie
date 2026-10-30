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

git ls-files .claude/settings.json:
  (no output — not tracked)

git log --oneline -- .claude/settings.json:
  (no output — never committed)

stat -c '%F %t,%T' .claude/settings.json:
  character special file 1,3

cat .claude/settings.json:
  (empty)

git status --short:
  ?? .bash_profile
  ?? .claude/settings.json
  ?? .mcp.json

cat .claude/settings.local.json:
```json
{
  "sandbox": {
    "enabled": true,
    "network": {"allowedDomains": ["github.com", "api.github.com", "pypi.org"]},
    "filesystem": {
      "denyRead": ["~/"],
      "allowRead": ["/home/alice/myrepo", "/home/alice/.cache"],
      "allowWrite": ["/home/alice/myrepo", "/home/alice/.cache"]
    }
  },
  "permissions": {
    "deny": ["Read(~/.aws/**)", "Bash(curl *)"],
    "ask": ["Bash(git push *)", "Bash(gh pr create *)"]
  }
}
```

cat ~/.claude/settings.json (sandbox and permissions only):
```json
{
  "permissions": {
    "deny": ["Edit(~/.claude/scripts/**)"]
  }
}
```

---

## Check 6 — Status-line prefix (sandbox.enabled resolution)

.claude/settings.local.json: sandbox.enabled = true
.claude/settings.json: sandbox placeholder (character special file 1,3), not tracked by git — absent on the host
~/.claude/settings.local.json: (not present)
~/.claude/settings.json: (no sandbox.enabled key)

Effective sandbox.enabled: true
