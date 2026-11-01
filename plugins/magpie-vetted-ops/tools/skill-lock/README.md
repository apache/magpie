<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [skill-lock](#skill-lock)
  - [Prerequisites](#prerequisites)
  - [Where the lock lives](#where-the-lock-lives)
  - [Liveness](#liveness)
  - [CLI](#cli)
  - [Where it is installed](#where-it-is-installed)
  - [How skills use it](#how-skills-use-it)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# skill-lock

**Capability:** substrate:action-guard

**Harness:** agnostic

A per-skill **write lock** for the batch skills. A sweep's read and
classify phase has no side effects and may run concurrently with
anything. Its write phase (posting triage comments, stale nudges, labels,
closes) must not: two overlapping runs of the same skill over the same
repository post the same comment or label twice, and a doubled bot
comment is exactly what makes contributors distrust the bot. The write
phase takes this lock first; a second run finds it held, stops, and says
who holds it.

## Prerequisites

- **Runtime:** Python 3.11+ via `uv`; stdlib only.
- **CLIs:** none.
- **Credentials / auth:** none.
- **Network:** none; works entirely on local files.

## Where the lock lives

`<personal layer>/run/locks/<skill>@<owner>__<repo>.lock/`, where the
personal layer is `.apache-magpie-local/` in an adopted project and the
git-directory home (`<git-common-dir>/apache-magpie/`) otherwise, the same
resolution every framework tool uses (`layers.py`). It is never inside the
working tree of an adopted project, so it can never be committed.

The lock is scoped to **skill and repository**: `issue-triage` on
`apache/a` and on `apache/b` never contend, and `issue-triage` and
`issue-stale-sweep` on the same repository never contend either, because
they post different things.

## Liveness

The process that runs `acquire` is an `uv run` that exits at once, and the
skill run that owns the lock is an agent session with no stable pid, so
liveness is a **lease**: the owner record carries an expiry (`--ttl`,
default 7200 s) and the write phase is expected to finish well inside
it. An expired lock is stale and is taken over by the next `acquire`;
`renew` extends a long run; pass the `--token` from `acquire` so a run
whose lease was taken over cannot extend the new holder's lock. A
takeover renames the stale lock to a unique tombstone first, so when two
runs find the same stale lock only one of them acquires it. A caller that does have a stable pid (a shell
script) passes `--owner-pid`, and a dead pid on the same host also counts
as stale.

## CLI

Every command prints one JSON object.

```bash
uvx --from ~/.claude/magpie/skill-lock skill-lock acquire <skill> --repo <owner/repo> [--ttl 7200] [--note "..."]
uvx --from ~/.claude/magpie/skill-lock skill-lock renew   <skill> --repo <owner/repo> [--ttl 7200] [--token <t>]
uvx --from ~/.claude/magpie/skill-lock skill-lock release <skill> --repo <owner/repo> [--token <t>] [--force]
uvx --from ~/.claude/magpie/skill-lock skill-lock status  <skill> --repo <owner/repo>
uvx --from ~/.claude/magpie/skill-lock skill-lock list
```

Exit codes for `acquire`:

| Exit | `status` | Meaning |
|---|---|---|
| 0 | `acquired` | Proceed. The result carries a `token`; pass it to `release`. |
| 3 | `already_running` | Another run holds the lock. Stop the write phase. The result carries the `holder` record (started, expires, note) and a `hint` with the `--force` release command for a run known to be dead. Not a failure of the sweep. |
| 2 | `error` | Could not create or read the lock; the result says why. |

`release` with `--token` refuses a non-matching holder (so a run never
releases a lock it did not take); without a token it releases
unconditionally, which is what the skill prose does at the end of its own
run. `--force` is the operator's override for a lock whose owner is known
to be gone before its lease expired.

`--root` names the project root explicitly; by default it is found from
the current directory (the nearest ancestor holding `.git`, `.svn` or
`.apache-magpie.lock`).

## Where it is installed

Skills run it as `uvx --from ~/.claude/magpie/skill-lock skill-lock …` on every
install. It ships inside the always-installed `magpie-vetted-ops` plugin, whose
session hook points `~/.claude/magpie/skill-lock` at the installed version, the
same way it links `~/.claude/magpie/vetted-ops`. The plugin cache is read-only,
which is why the launcher is `uvx --from` (it builds into uv's cache) rather than
`uv run --project` (which would need to write a venv into the plugin). It runs
inside the sandbox and needs no exclusion: it touches only the lock directory.

## How skills use it

The shared prose block [`tools/dev/blocks/write-lock.md`](https://github.com/apache/magpie/blob/main/tools/dev/blocks/write-lock.md)
is propagated into the write step of every batch skill that posts:
`issue-triage`, `security-issue-triage`, `issue-stale-sweep`,
`pr-stale-sweep`, `pr-management-triage` and `good-first-issue-sweep`.
Read-only skills take no lock. The block says: acquire before the first
write, stop on `already_running` and show the holder, release after the
recap, and release in the stop-and-surface path too so a failed post never
leaves a lock behind for its lease length.

## Tests

```bash
uv run --directory tools/skill-lock --group dev pytest
```
