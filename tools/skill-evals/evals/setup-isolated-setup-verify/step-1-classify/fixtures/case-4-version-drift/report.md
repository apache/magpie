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
  ref: v0.9.2

Result: ref differs (local v0.9.2, committed pin v0.9.1) — sync needed.

---

## Check 1 — Project .claude/settings.json

cat .claude/settings.json:
```json
{
  "sandbox": {
    "enabled": true,
    "network": {"allowedDomains": ["github.com", "api.github.com", "pypi.org"]},
    "filesystem": {
      "allowRead": ["/home/carol/magpie", "/tmp/claude"],
      "allowWrite": ["/home/carol/magpie", "/tmp/claude"]
    }
  },
  "permissions": {
    "deny": ["Bash(cat ~/.aws/*:*)", "Bash(curl:*)", "Bash(wget:*)"],
    "ask": ["Bash(git push:*)", "Bash(gh pr create:*)"]
  }
}
```

---

## Check 2 — User-scope ~/.claude/settings.json

cat ~/.claude/settings.json:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "~/.claude/scripts/sandbox-bypass-warn.sh"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "~/.claude/scripts/sandbox-error-hint.sh"}]
      }
    ]
  },
  "statusLine": "~/.claude/scripts/sandbox-status-line.sh"
}
```

---

## Check 3 — Hook scripts present and executable

ls -la ~/.claude/scripts/:
  -rwxr-xr-x  carol  staff  sandbox-bypass-warn.sh
  -rwxr-xr-x  carol  staff  sandbox-error-hint.sh
  -rwxr-xr-x  carol  staff  sandbox-status-line.sh

---

## Check 4 — claude-iso sourced

grep claude-iso ~/.zshrc:
  source ~/.claude/scripts/agent-iso.sh

grep "alias claude=" ~/.zshrc:
  alias claude='claude-iso'

---

## Check 5 — Pinned tool versions

tools/agent-isolation/pinned-versions.toml [tools.claude-code]:
  version = "2.1.150"

Installed (claude --version):
  2.2.0

---

## Check 6 — Status-line prefix (sandbox.enabled resolution)

.claude/settings.local.json: (not present)
.claude/settings.json: sandbox.enabled = true
~/.claude/settings.local.json: (not present)
~/.claude/settings.json: (no sandbox key)

Effective sandbox.enabled: true

---

## Check 7 — Denial commands

cat ~/.aws/credentials:
  Operation not permitted

echo $AWS_ACCESS_KEY_ID:
  (empty)

curl https://example.com:
  Permission to use Bash with command 'curl https://example.com' has been denied.

---

## Check 8 — Project-root coverage in sandbox allowlists

CWD: /home/carol/magpie

cat .claude/settings.local.json:
```json
{
  "sandbox": {
    "filesystem": {
      "allowRead": ["/home/carol/magpie"],
      "allowWrite": ["/home/carol/magpie"]
    }
  }
}
```

/home/carol/magpie found in allowRead: yes
/home/carol/magpie found in allowWrite: yes

Live probe:
  Read .git/HEAD: OK (content: "ref: refs/heads/main")
  Write .magpie-verify-probe.tmp: OK (removed)
