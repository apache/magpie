<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Framework checkout (local self-adoption). Personal layer: `.apache-magpie-local/`. Isolated setup: configured.

Findings:
- slug: gateway-hook-older-version. `~/.claude/scripts/container-gateway-hook.sh` differs from `tools/agent-isolation/container-gateway-hook.sh`.
  The diff shows 2 lines present in the user-scope copy that the framework copy no longer has, replaced by 3 new lines that fix a security problem.
  Gather looked the copy's blob hash up in the framework checkout's history of that file: it matches the version shipped two releases ago, so the copy is an older shipped version, not a local edit.
  Writing `~/.claude/scripts/` is outside the sandbox write scope.
