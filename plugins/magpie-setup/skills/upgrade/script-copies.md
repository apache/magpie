<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# User-scope script copies

Read when a user-scope script copy differs from its framework source.

## Gather: stale copy or local edits

A user-scope script copy that differs from its framework source may be an older shipped version or may carry the user's own edits.
Where the framework's full git history is readable inside the sandbox (a framework checkout for which `git rev-parse --is-shallow-repository` prints `false`), look up the copy's blob hash (`git hash-object`) in `git log --raw --no-abbrev --format= -- <source>`.
A match means the copy is an older shipped version: it is stale.
No match means local edits.
With no history to look in, or only part of it (a marketplace or snapshot install, or a shallow clone), the two cannot be told apart: record the lines only the installed copy has, for the plan to show.

## Plan: script copies

**Script copies.** Only a copy listed under *Plain content diffs* in [`script-inventory.md`](../isolated-setup-update/script-inventory.md) can be a plan item.
Anything else goes under *Run these yourself* as a re-run of the [`setup-isolated-setup-install`](../isolated-setup-install/SKILL.md) step that installs it:
the `gpg-touch-wrap-*` symlinks and `shims/` are Step K, a `~/.claude/git-hooks/` flavour is Step P.3, the `container_gateway` package is Step L, the `skill_evals` package with `magpie-run-evals.sh` is Step M, and `agent-guard.py` with `guards.d` is the agent-guard wiring of Step P.
A copy Gather found to be an older shipped version is stale: *Update*, or *Fix* when the framework copy carries a security fix.
A copy with local edits goes under *Still open* with its diff path.
A copy that could not be told apart (no history to compare, or only a shallow clone's) is an *Update* or *Fix* item whose line ends `(replaces N lines only this copy has)`.
Its `details <n>` lists those lines, and its bypassed call saves the old copy to the scratch directory before writing.
This deliberately relaxes `setup-isolated-setup-update`'s "never re-`cp`" for plain-content copies only, under the checksum rule.

## Apply: local edits are never a plain overwrite

3. **Local edits are never a plain overwrite.**
   A user-scope script copy with local edits is skipped with its diff written to the scratch directory; *Still open* names the diff path.
   Gather should already have kept such a copy out of the plan; this is the last guard.
   An item marked `(replaces N lines only this copy has)` saves the old copy to the scratch directory in the same bypassed call, before writing, and *Done* names that path.
