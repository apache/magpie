<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

cd ~/.claude-config: directory exists.

ls -la ~/.claude-config: contains CLAUDE.md and scripts/, but there is
no .git/ directory.

git -C ~/.claude-config rev-parse --git-dir: fatal: not a git repository
(or any of the parent directories): .git

Unable to proceed — ~/.claude-config exists but is not a git working tree.
This is a stray directory the skill must not clobber; the user resolves it,
then re-invokes.
