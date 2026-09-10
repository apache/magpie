<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Pre-flight — is this project set up?](#pre-flight--is-this-project-set-up)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Pre-flight — is this project set up?

Do this **first, before anything else in this skill**, and do it silently: on
the happy path it costs three file checks and prints nothing.

A marketplace install delivers *skills only*. Nothing in it configures this
repository, and on most harnesses **no code runs at all** when a plugin is
installed or upgraded — there is no post-install step to rely on. Claude Code's
`SessionStart` hook covers only the all-in-one plugin, so for every other
install this check is the one thing standing between a stale or unadopted repo
and a skill that acts on wrong assumptions.

1. **Is a lock present?** If `.apache-magpie.lock` exists, this project uses the
   pinned-snapshot install. Compare it with `.apache-magpie.local.lock`:
   - local lock missing → the snapshot was never fetched on this machine;
   - `ref` / `commit` differ → this machine is on a different framework version
     than the project pins.
2. **No lock?** Then this is the marketplace install (or nothing at all). Look
   for a `<project-config>/` directory. If there is none, the project has not
   been adopted and every `<placeholder>` in this skill is unresolved.
3. **Anything unresolved above → stop and propose `/magpie-setup`** (or
   `/magpie-setup upgrade` for a version mismatch). Say which of the three
   checks failed and what you found. Do **not** run setup unattended and do
   **not** continue this skill on a guess: a skill that proceeds against an
   unadopted repo writes to the wrong tracker.

Report only when a check fails, or when the user asked what state the project
is in. `/magpie-setup verify` is the full diagnostic — this is deliberately the
cheap subset that is worth paying for on every invocation.
