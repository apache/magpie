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

.claude/settings.json: sandbox.enabled: true; permissions.deny and permissions.ask present;
sandbox.network.allowedDomains and sandbox.filesystem denyRead ["~/"] and allowRead/allowWrite configured.
.claude/settings.local.json: project-root allowRead/allowWrite entries only.

---

## Check 10 — Hardware-key touch overlay and the signing key

git config --get commit.gpgsign: true
git config --get gpg.format: ssh
git config --get user.signingkey: /home/alice/.ssh/id_ed25519.pub

cut -d' ' -f1 /home/alice/.ssh/id_ed25519.pub:
  ssh-ed25519

echo $SSH_AUTH_SOCK:
  /run/user/1000/keyring/ssh

10a — wiring and scripts:
  ~/.claude/settings.json: no gpg-touch-overlay.sh hook on PreToolUse or PostToolUse
  ~/.claude/scripts/gpg-touch-overlay.sh: not present

10b — the window can draw: not run

10c — signing key readable in the sandbox:
  head -c 1 "$(git config --get user.signingkey)" >/dev/null
  rc=0

10d — git's own programs:
  git config --global --get gpg.ssh.program: (unset)
  git config --global --get core.sshCommand: (unset)

10e — ssh shim directory:
  ~/.claude/scripts/shims/: not present
