<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-7 — a required config file is missing

Running `/magpie-setup config` unasked is safe because of what it touches:
only the personal layer — `<git-common-dir>/apache-magpie/` when the
project has not adopted Magpie, the gitignored `.apache-magpie-local/` when
it has (the main checkout's, from a linked worktree that has none) — which
is invisible to every other person and every other clone and undone by
deleting a directory. It stages nothing, commits nothing, writes nothing
into the working tree of an unadopted project, and changes nothing about
the repository anyone else sees.

Unlike a plugin below the floor, this needs no restart: the files are
written and read in the same turn, so the interruption ends and the command
proceeds.

The two prohibitions are in the block itself because they bind whether or
not this file was read: never fabricate a value, and never continue past a
value the skill needs but does not have.
