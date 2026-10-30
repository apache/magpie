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

## Framework checkout

Current repository: /home/alice/myrepo — not the framework (no tools/agent-isolation/pinned-versions.toml)
.apache-magpie/ snapshot: not present
grep agent-iso ~/.bashrc (run by the user outside the sandbox): [ -f "$HOME/.claude/agent-isolation/agent-iso.sh" ] && . "$HOME/.claude/agent-isolation/agent-iso.sh" — a user-scope copy, not a checkout
Asked the user for a checkout path: "I don't have a magpie clone, I installed from the marketplace."

Result: no framework checkout.

---

## Check 5 — Tool versions

bwrap --version: bubblewrap 0.11.2
socat -V: socat version 1.8.1.3
command claude --version: 2.1.210 (Claude Code)
Harness: Claude Code
tools/agent-isolation/pinned-versions.toml: not available (no framework checkout)

---

## Check 10 — Hardware-key touch overlay and the signing key

git config --get commit.gpgsign: true
git config --get gpg.format: ssh
git config --get user.signingkey: /home/alice/.ssh/id_ed25519_sk.pub
cut -d' ' -f1 /home/alice/.ssh/id_ed25519_sk.pub: sk-ssh-ed25519@openssh.com

10a — wiring and scripts:
  PreToolUse Bash → ~/.claude/scripts/gpg-touch-overlay.sh arm
  PostToolUse, PermissionDenied, PostToolUseFailure Bash → ~/.claude/scripts/gpg-touch-overlay.sh disarm
  ~/.claude/scripts/gpg-touch-overlay.sh: -rwxr-xr-x
  ~/.claude/scripts/gpg-touch-overlay-window.py: -rwxr-xr-x
  Comparison against tools/agent-isolation/: not possible (no framework checkout)

10b — the window can draw (run by the user with the ! prefix):
  rc=0

10c — signing key readable in the sandbox:
  head -c 1 "$(git config --get user.signingkey)" >/dev/null
  rc=0

10d — git's own programs:
  git config --global --get gpg.ssh.program: /home/alice/.claude/scripts/gpg-touch-wrap-ssh-keygen → resolves to ~/.claude/scripts/gpg-touch-overlay.sh
  git config --global --get core.sshCommand: ~/.claude/scripts/gpg-touch-overlay.sh wrap ssh
  head -c 1 on both wrapper files from the sandbox: rc=0

10e — ssh shim directory:
  ~/.claude/scripts/shims/: not present

---

## Check 13 — Eval-harness exclusion

sandbox.excludedCommands: contains "~/.claude/scripts/magpie-run-evals.sh *"
~/.claude/scripts/magpie-run-evals.sh: -rwxr-xr-x
~/.claude/scripts/skill-evals/src/skill_evals/: present
permissions.deny: contains Edit(~/.claude/scripts/**)
13c — comparison against tools/skill-evals/: not possible (no framework checkout)
