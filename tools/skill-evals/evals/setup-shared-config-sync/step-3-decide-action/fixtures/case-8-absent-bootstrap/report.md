<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

cd ~/.claude-config: directory does not exist.

ls ~/: no .claude-config directory found — the path is entirely absent.

~/.claude-config has never been set up on this host. Rather than stopping,
the skill bootstraps it: resolve the default remote
(git@github.com:<handle>/claude-config.git, or an explicit URL the user
passed), check whether that remote already exists, then clone it if it does
or create a new private remote and scaffold the minimal layout if it does not.
