<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

1. Enumerate worktrees with `git worktree list --porcelain`.
   Filter to linked worktrees only — skip the main checkout
   (already handled earlier in this run) and skip any bare
   worktrees.
2. If the list is empty, this pass is a no-op; record "no
   linked worktrees" in the recap and continue.
3. For each linked worktree, invoke
   `setup worktree-init` with that worktree's
   working directory as the `cwd`. The sub-action picks up
   the family set from `<main>/.apache-magpie.lock` (the
   committed lock the worktree shares via git) plus the
   always-on families per
   [`SKILL.md` Golden rule 8](SKILL.md#golden-rules), and
   reconciles both the snapshot symlink and the canonical +
   relay framework-skill symlinks (see
   [`worktree-init.md` Step 1 + Step 1b](worktree-init.md)).
