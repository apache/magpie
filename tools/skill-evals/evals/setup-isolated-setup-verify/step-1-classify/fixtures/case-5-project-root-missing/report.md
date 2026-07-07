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
      "allowRead": ["/tmp/claude", "$TMPDIR"],
      "allowWrite": ["/tmp/claude", "$TMPDIR"]
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
  -rwxr-xr-x  dave  staff  sandbox-bypass-warn.sh
  -rwxr-xr-x  dave  staff  sandbox-error-hint.sh
  -rwxr-xr-x  dave  staff  sandbox-status-line.sh

---

## Check 4 — claude-iso sourced

grep claude-iso ~/.bashrc:
  source ~/.claude/scripts/agent-iso.sh

grep "alias claude=" ~/.bashrc:
  (no match)

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

CWD: /home/dave/tracker-repo

cat .claude/settings.local.json:
  (file not present)

.claude/settings.local.json not found — /home/dave/tracker-repo is NOT in allowRead or allowWrite.

git worktree list --porcelain:
  worktree /home/dave/tracker-repo
  HEAD def456
  branch refs/heads/main

  worktree /home/dave/tracker-repo-feat
  HEAD ghi789
  branch refs/heads/feat/my-feature

  cat /home/dave/tracker-repo-feat/.claude/settings.local.json:
  (file not present)

Live probe:
  Read .git/HEAD: FAILED — Operation not permitted (sandbox blocked the read)
  Write .magpie-verify-probe.tmp: FAILED — Operation not permitted
