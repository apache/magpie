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

## Check 7 — Denial commands

test -r <path>, for each of ~/.aws/credentials, ~/.ssh/id_ed25519, ~/.config/gh/hosts.yml, ~/.netrc, ~/.docker/config.json:
  rc=1 for every path

stat -c '%F %t,%T' <path>, for each of the same paths:
  stat: cannot statx '<path>': No such file or directory

ls ~/.aws/credentials ~/.config/gh/hosts.yml (run by the user from their own terminal):
  /home/alice/.aws/credentials
  /home/alice/.config/gh/hosts.yml

env | cut -d= -f1 | sort:
  AZURE_OPENAI_API_KEY
  CLAUDECODE
  CLAUDE_CODE_ENTRYPOINT
  GITHUB_TOKEN
  HOME
  LANG
  PATH
  PWD
  SHELL
  SSH_AUTH_SOCK
  TERM
  TMPDIR
  USER
  VSCODE_GIT_IPC_HANDLE

echo $CLAUDE_CODE_ENTRYPOINT:
  claude-vscode

curl https://example.com:
  Permission to use Bash with command 'curl https://example.com' has been denied.
