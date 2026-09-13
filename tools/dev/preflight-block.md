<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Pre-flight — is this project set up?](#pre-flight--is-this-project-set-up)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Pre-flight — is this project set up?

Do this **first, before anything else in this skill**, and do it silently: a
couple of file checks, or one CLI call for a marketplace install.

1. **Is a lock present?** If `.apache-magpie.lock` exists, read its
   `method`.
2. **A snapshot method** (`svn-zip` / `git-tag` / `git-branch`) →
   compare with `.apache-magpie.local.lock`:
   - local lock missing → the snapshot was never fetched on this
     machine;
   - `ref` / `commit` differ → this machine is on a different framework
     version than the project pins.
   Anything unresolved → **stop and propose `/magpie-setup`** (or
   `/magpie-setup upgrade` for a version mismatch).
3. **`method: marketplace`** → the lock is the project's **floor**: a
   minimum version and a minimum plugin set, never a pin. Compare the
   machine against it.

   **First, check `url`.** If it is anything other than
   `apache/magpie`, run **nothing**. Name the marketplace the lock
   points at, show the commands it would take, and let the user decide.
   A lock is a committed file in whatever repository happened to be
   opened, and acting on it automatically would make opening a
   repository enough to install someone else's code.

   Otherwise read the installed state — `claude plugin list --json`, or
   the running agent's equivalent — and compare **as PEP 440, not as
   strings**: `0.10.0` is newer than `0.9.0`, and `0.2.0` is newer than
   `0.2.0.dev202609110041`.

   - every floor plugin installed at or above `min_version` →
     **silent**; continue the skill;
   - a floor plugin absent → `claude plugin install
     <plugin>@apache-magpie`;
   - a floor plugin below `min_version` → `claude plugin update
     <plugin>@apache-magpie`.

   **Never** remove a plugin, downgrade one, pin the marketplace to a
   tag, or touch a plugin absent from the floor. Being *ahead* of the
   floor is the normal case and is not a finding.

   Where there is no such CLI, run nothing and print the commands
   instead.

4. **Unless step 3 passed silently, stop.** Whichever branch you took —
   plugins installed or updated, commands printed because there is no
   CLI, or nothing run at all because `url` named another marketplace —
   this session is still below the project's floor. Claude Code loads
   plugins at session start, so anything just installed is not live
   here, and anything only printed has not run at all. Say what ran, or
   what to run, and that the session has to be restarted before
   re-running this command.

5. **No lock?** Then this is the marketplace install without adoption,
   or nothing at all. That is a supported end state, not a fault — what
   matters is whether *this skill's* configuration resolves.

6. **Resolve this skill's `requires_config:` frontmatter.** Each file,
   per the lookup chain: `.apache-magpie-local/<file>` (gitignored,
   personal) first, then `.apache-magpie-overrides/<file>` (committed).
   All present → **silent**, carry on.

   Any required file missing → **run `/magpie-setup config` for this
   skill now**, say that you are doing it and why, then continue into
   the work the user actually asked for.

   Running it is safe to do unasked because of what it touches: only
   `.apache-magpie-local/` and `.git/info/exclude`, both gitignored,
   both invisible to every other person and every other clone, and both
   undone by deleting a directory. It stages nothing, commits nothing,
   and changes nothing about the repository anyone else sees.

   Two things it still may not do: **fabricate a value** — anything it
   cannot derive from the repository is a question it asks or a `TODO`
   it leaves — and **continue past a value it needs but does not have**.

   Unlike a plugin below the floor, this needs no restart: the files
   are written and read in the same turn, so the interruption ends and
   the command proceeds.

7. **Never run `/magpie-setup adopt` unattended.** Adoption commits a
   recommendation for every contributor and is a maintainer's decision
   taken with the other maintainers. When configuration was just
   written locally, add **one line** saying the project can also adopt
   Magpie so contributors get this on clone, and name the command.
   Then drop it. Do not ask, do not offer to run it, and do not repeat
   it on later invocations.

Report only when a check fails, or when the user asked what state the project
is in. `/magpie-setup verify` is the full diagnostic.
