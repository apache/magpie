<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-12 — personal config still in the working tree

This repository has not adopted Magpie (there is no `.apache-magpie.lock`),
yet it still has the old in-tree `.apache-magpie-local/` directory
(`facts.legacy_dir`).
A project that has not adopted Magpie should carry nothing of it in its working tree.
Personal configuration for such a project now lives in `facts.personal_dir`,
inside the repository's git directory: never committed, never needing an ignore entry,
and shared by every worktree of the clone.

Nothing is broken and this is not a stop.
The legacy directory is still read, after `facts.personal_dir`, so carry on with the work the user asked for
and mention the move once, at a natural pause.

**Propose the move; never make it silently.**
Show the user exactly what would happen and wait for an explicit yes:

1. move the contents of `facts.legacy_dir` into `facts.personal_dir`
   (creating it if `facts.personal_dir_exists` is false);
   where a file exists in both, show both and let the user choose — never overwrite;
2. remove the now-empty `facts.legacy_dir`;
3. if `facts.exclude_has_entry` is true, remove the `/.apache-magpie-local/` line from `facts.exclude_file`
   and leave every other line untouched;
4. if `.claude/settings.local.json` names container-gateway sockets under `facts.legacy_dir`'s `run/`
   (`CONTAINER_HOST`, `DOCKER_HOST`, `sandbox.network.allowUnixSockets`),
   show the same entries rewritten to `<facts.personal_dir>/run/<worktree-id>/` (`main`, or the linked worktree's `.git/worktrees/<name>` name), where the gateway now serves from.
   Do not move a live socket: the gateway recreates its sockets in the new place on its next start.

**Nothing moves without the user's confirmation.**
A declined move is fine: the legacy directory keeps working for configuration (gateway sockets already serve from `<facts.personal_dir>/run/<worktree-id>/` (`main`, or the linked worktree's `.git/worktrees/<name>` name)), and the finding repeats on later runs until the directory is gone.

If `facts.personal_dir` is null, the project is not a git repository and there is nowhere outside the working tree to keep personal config.
Leave the directory where it is and say so; do not propose a move.
