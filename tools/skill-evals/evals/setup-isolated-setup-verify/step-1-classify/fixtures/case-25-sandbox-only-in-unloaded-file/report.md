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

cat .claude/settings.local.json:
  (not present)

cat .claude/settings.json:
```json
{
  "permissions": {
    "deny": ["Read(~/.aws/**)", "Bash(curl *)"],
    "ask": ["Bash(git push *)", "Bash(gh pr create *)"]
  }
}
```

cat ~/.claude/settings.json (sandbox and permissions only):
```json
{
  "sandbox": {
    "network": {"allowedDomains": ["github.com", "api.github.com", "pypi.org"]},
    "filesystem": {
      "denyRead": ["~/"],
      "allowRead": ["/home/alice/myrepo"],
      "allowWrite": ["/home/alice/myrepo"]
    }
  }
}
```

---

## Check 6 — Status-line prefix (sandbox.enabled resolution)

.claude/settings.local.json: (not present)
.claude/settings.json: (no sandbox key)
~/.claude/settings.json: (no sandbox.enabled key)

Not in the walk, read to diagnose:
~/.claude/settings.local.json: sandbox.enabled = true

Effective sandbox.enabled: not set
