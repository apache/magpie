<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-7 — a required config file is missing

Running `/magpie-setup config` unasked is safe because of what it touches:
only `.apache-magpie-local/` and `.git/info/exclude`, both gitignored, both
invisible to every other person and every other clone, and both undone by
deleting a directory. It stages nothing, commits nothing, and changes
nothing about the repository anyone else sees.

Unlike a plugin below the floor, this needs no restart: the files are
written and read in the same turn, so the interruption ends and the command
proceeds.

The two prohibitions are in the block itself because they bind whether or
not this file was read: never fabricate a value, and never continue past a
value the skill needs but does not have.
