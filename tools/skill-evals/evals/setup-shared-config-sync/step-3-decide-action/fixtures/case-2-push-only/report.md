<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

cd ~/.claude-config: OK — valid git working tree.
Remote: git@github.com:alice-private/claude-config.git

git fetch origin: (no output — remote already up to date)

git status --short: (no output — working tree clean)

git log origin/main..HEAD:
  abc1234 scripts: increase pull cooldown from 300s to 600s

Commits ahead of origin/main: 1
Commits behind origin/main: 0

Lock file: ~/.claude-config/.sync.lock not present.
