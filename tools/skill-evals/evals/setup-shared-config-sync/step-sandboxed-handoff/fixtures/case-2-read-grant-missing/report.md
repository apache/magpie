<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The agent runs inside the secure-setup sandbox. `sandbox.filesystem.denyRead`
covers `~/`, and no `allowRead` entry covers `~/.claude-config/`.

git -C ~/.claude-config --no-optional-locks status:
  fatal: Unable to read current working directory: Operation not permitted

The user asked to sync the config repo.
