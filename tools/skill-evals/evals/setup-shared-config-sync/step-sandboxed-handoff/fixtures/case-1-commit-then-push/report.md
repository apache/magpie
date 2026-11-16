<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The agent runs inside the secure-setup sandbox. `~/.claude-config/` is in
`sandbox.filesystem.allowRead`; no write grant covers it.

git -C ~/.claude-config --no-optional-locks status --short --branch:
  ## main...origin/main
   M CLAUDE.md

The user approved committing CLAUDE.md with the subject
"CLAUDE.md: pass --repo with adversarial-review pr targets".
