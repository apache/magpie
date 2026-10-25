<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Approved plan as shown:
1. slug checker-copy-stale (Update)
2. slug mentoring-config-missing (Add)
3. slug allowlist-worktrees (Add), not marked [bypass]

User reply: `yes`.
Re-check of targets before writing:
- checker-copy-stale: unchanged.
- mentoring-config-missing: the target file `mentoring-config.md` now exists; its checksum differs from what Gather recorded (another session created it, with content).
- allowlist-worktrees: unchanged.
Every run that proceeds succeeds.
