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
    "network": {"allowedDomains": ["github.com", "api.github.com"]},
    "filesystem": {
      "allowRead": ["/home/bob/tracker", "/tmp/claude"],
      "allowWrite": ["/home/bob/tracker", "/tmp/claude"]
    }
  },
  "permissions": {
    "deny": ["Bash(cat ~/.aws/*:*)", "Bash(curl:*)"],
    "ask": ["Bash(git push:*)"]
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
    ]
  },
  "statusLine": "~/.claude/scripts/sandbox-status-line.sh"
}
```

PostToolUse hook for sandbox-error-hint.sh: not configured.

---

## Check 3 — Hook scripts present and executable

ls -la ~/.claude/scripts/:
  (directory does not exist)

---

## Check 4 — claude-iso sourced

grep claude-iso ~/.bashrc:
  source ~/.claude/scripts/agent-iso.sh

grep "alias claude=" ~/.bashrc:
  alias claude='claude-iso'

---

## Check 5 — Pinned tool versions

tools/agent-isolation/pinned-versions.toml [tools.claude-code]:
  version = "2.1.150"

Installed (claude --version):
  2.1.150

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

CWD: /home/bob/tracker

cat .claude/settings.local.json:
```json
{
  "sandbox": {
    "filesystem": {
      "allowRead": ["/home/bob/tracker"],
      "allowWrite": ["/home/bob/tracker"]
    }
  }
}
```

/home/bob/tracker found in allowRead: yes
/home/bob/tracker found in allowWrite: yes

Live probe:
  Read .git/HEAD: OK (content: "ref: refs/heads/main")
  Write .magpie-verify-probe.tmp: OK (removed)
