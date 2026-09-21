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

sandbox.enabled: true; permissions.deny and permissions.ask present;
sandbox.network.allowedDomains and sandbox.filesystem allowRead/allowWrite configured.

## Check 2 — User-scope ~/.claude/settings.json wiring

PreToolUse Bash → ~/.claude/scripts/sandbox-bypass-warn.sh
PostToolUse Bash → ~/.claude/scripts/sandbox-error-hint.sh
statusLine → ~/.claude/scripts/sandbox-status-line.sh

## Check 3 — Hook scripts

sandbox-bypass-warn.sh: -rwxr-xr-x
sandbox-error-hint.sh: -rwxr-xr-x
sandbox-status-line.sh: -rwxr-xr-x

## Check 4 — claude-iso

grep agent-iso ~/.zshrc: source ~/.claude/agent-isolation/agent-iso.sh
alias claude='claude-iso': not set (optional)

## Check 5 — Tool versions

macOS: bubblewrap / socat not applicable (Seatbelt).
claude --version: 2.1.150 ; min_version floor: 2.1.150 → at floor.

## Check 6 — Status line

Session status line shows [sandbox].

## Check 7 — Denial commands

cat ~/.aws/credentials: Operation not permitted
echo $AWS_ACCESS_KEY_ID: (empty)
curl https://example.com: Permission to use Bash with command 'curl https://example.com' has been denied.

## Check 8 — Project-root coverage

/Users/alice/tracker in allowRead: yes; in allowWrite: yes (.claude/settings.local.json)
git worktree list: one worktree.
Live probe: read .git/HEAD OK; write .magpie-verify-probe.tmp OK (removed).

## Check 9 — vetted-ops split and exclusion

permissions.allow contains vetted-op-read only; vetted-op is in ask.
permissions.deny has Edit on ~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/** and .apache-magpie-overrides/tools/vetted-ops/**.

## Check 10 — Hardware-key touch overlay and the signing key

git config --get commit.gpgsign: true
git config --get gpg.format: ssh
git config --get user.signingkey: /Users/alice/.ssh/id_ed25519_sk.pub

10a — wiring and scripts:
  PreToolUse Bash → ~/.claude/scripts/gpg-touch-overlay.sh arm
  PostToolUse Bash → ~/.claude/scripts/gpg-touch-overlay.sh disarm
  ~/.claude/scripts/gpg-touch-overlay.sh: -rwxr-xr-x, identical to tools/agent-isolation/gpg-touch-overlay.sh
  ~/.claude/scripts/gpg-touch-overlay-window-macos.py: -rwxr-xr-x, identical to tools/agent-isolation/gpg-touch-overlay-window-macos.py

10b — the window can draw (run by the user with the ! prefix, outside the sandbox):
  ! ~/.claude/scripts/gpg-touch-overlay.sh _gui_available ; echo rc=$?
  rc=0

10c — signing key readable in the sandbox:
  head -c 1 "$(git config --get user.signingkey)" >/dev/null
  head: /Users/alice/.ssh/id_ed25519_sk.pub: Operation not permitted
  sandbox.filesystem.allowRead in ~/.claude/settings.json: no entry for ~/.ssh/id_ed25519_sk.pub
