<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Approved plan as shown:
1. slug checker-copy-stale (Update)
2. [bypass] slug claude-config-diff (Check)

User reply: `yes`.
Re-check of targets: unchanged. Item 1 succeeds.
Item 2, the `~/.claude-config` diff run outside the sandbox, completes and shows one more stale file: slug claude-config-sync-script-stale (a script copy with no local-only lines).
That fix was not in the approved plan.
