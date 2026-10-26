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
.claude/settings.local.json: project-root allowRead/allowWrite entries only; no allowRead entry under ~/ besides the project root.

---

## Check 7 — Denial commands

test -r <path>, for each of ~/.aws/credentials, ~/.ssh/id_ed25519, ~/.config/gh/hosts.yml, ~/.netrc, ~/.docker/config.json:
  rc=1 for every path

stat -c '%F %t,%T' <path>, for each of the same paths:
  stat: cannot statx '<path>': No such file or directory

Sentinel: none available — no file under ~/ has been confirmed to exist on the host in this run (check 4 has not been run outside the sandbox yet).

ls of the candidates from the user's own terminal: not run yet.

env | cut -d= -f1 | sort:
  CLAUDECODE CLAUDE_CODE_ENTRYPOINT HOME LANG PATH PWD SHELL SSH_AUTH_SOCK TERM TMPDIR USER

echo $CLAUDE_CODE_ENTRYPOINT:
  cli

curl https://example.com:
  Permission to use Bash with command 'curl https://example.com' has been denied.
