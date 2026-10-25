<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. The run is in a linked worktree `/work/proj/.worktrees/feature-x` of the adopted project whose main checkout is `/work/proj`.
`python3 -m setup_preflight.layers` prints `personal_dir: /work/proj/.apache-magpie-local`.
The worktree has no `.apache-magpie-local/`. Isolated setup: configured.

Findings:
- slug: mentoring-config-main-checkout. `mentoring-config.md` is required by the installed `mentor` skill and absent from the personal layer.
  Scaffold it at `/work/proj/.apache-magpie-local/mentoring-config.md` (inside the sandbox write scope).
