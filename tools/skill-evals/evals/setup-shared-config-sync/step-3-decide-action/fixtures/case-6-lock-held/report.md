<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

cd ~/.claude-config: OK — valid git working tree.
Remote: git@github.com:alice-private/claude-config.git

git fetch origin: (no output — remote already up to date)

git status --short:
   M scripts/update.sh

Commits ahead of origin/main: 0
Commits behind origin/main: 0

Lock file: ~/.claude-config/.sync.lock is held.
  flock --nonblock ~/.claude-config/.sync.lock → exit code 1 (lock already held)
  Lock owner PID: 48321 (sync.sh timer, started ~30 seconds ago)
