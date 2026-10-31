<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Per-skill write lock for batch skills
status: experimental
kind: feature
mode: infra
source: >
  Two overlapping runs of one batch skill over one repository post the
  same comment or label twice. Implemented by tools/skill-lock/ and the
  shared prose block tools/dev/blocks/write-lock.md propagated into the
  write step of issue-triage, security-issue-triage, issue-stale-sweep,
  pr-stale-sweep, pr-management-triage and good-first-issue-sweep.
acceptance:
  - The write phase of every batch skill that posts, labels or closes takes
    a lock scoped to that skill and the target repository before its first
    write, and releases it after the recap and on the failure path.
  - A second run that finds the lock held posts nothing, shows the holder,
    and reports it as "another run is writing", not as a failure.
  - Read-only steps and read-only skills take no lock and may run
    concurrently.
  - The lock lives in the personal config layer, never in the working tree
    of an adopted project, and is never committed.
  - An expired lease, or a dead owner pid on the same host, is stale and is
    taken over; a lock with no readable owner is respected.
  - Different skills, and the same skill on different repositories, never
    contend.
---

# Per-skill write lock for batch skills

## What it does

Makes a batch skill's **write phase** single-flight per skill per
repository. A sweep's read and classify phase is side-effect free and may
overlap with anything; its posting phase is not. When two runs of
`issue-triage` over the same repository overlap, whether a maintainer
started one while a scheduled one was still posting or two maintainers
ran it at once, both post the same proposal comment on the same issue.
The lock stops the second run at the door of its write step, tells the
maintainer who holds it, and lets the first finish.

## Where it lives

- `tools/skill-lock/`: the lock tool. `skill-lock acquire | release |
  renew | status | list`, one JSON object per call, exit `0` acquired,
  `3` already running, `2` error. Stdlib only. `layers.py` is the shared
  personal-layer resolver (a verbatim copy checked by
  `tools/setup-preflight/tests/test_layers.py`).
- `plugins/magpie-vetted-ops/`: ships the tool on every install; its
  session hook (`tools/vetted-ops/hooks/link-stable-path.sh`) links
  `~/.claude/magpie/skill-lock`, and skills run it with
  `uvx --from ~/.claude/magpie/skill-lock skill-lock …` because the plugin
  cache is read-only.
- `tools/dev/blocks/write-lock.md`: the shared prose block, propagated by
  `tools/dev/check-shared-blocks.py --fix` into the write step of each
  batch skill, with `{override_name}` rendered to the skill's own name.
- `skills/issue-triage/compose-and-post.md`,
  `skills/issue-stale-sweep/posting-and-close.md`,
  `skills/pr-management-triage/interaction-loop.md`,
  `skills/security-issue-triage/SKILL.md`, `skills/pr-stale-sweep/SKILL.md`,
  `skills/good-first-issue-sweep/SKILL.md`: the propagated copies, at the
  "post sequentially" / "apply" / "execute" step.
- `docs/labels-and-capabilities.md`: the `substrate:action-guard` row for
  the tool.

## Behaviour & contract

- **Scope.** `<skill>@<owner>__<repo>`. Two skills on one repository
  never contend (they post different things); one skill on two
  repositories never contends.
- **Location.** `<personal layer>/run/locks/<scope>.lock/`, resolved the
  way every framework tool resolves the personal layer: the gitignored
  `.apache-magpie-local/` in an adopted project, the git-directory home
  otherwise. Never the working tree of an adopted project.
- **Mechanism.** Atomic `mkdir` plus one `owner.json` (skill, repo,
  token, pid, host, started, expires, note). No `flock`, nothing under
  `.git/` of an adopted project.
- **Liveness is a lease.** `acquire` runs as a short `uv run`, and the
  owning skill run is an agent session with no stable pid, so the owner
  record carries an expiry (`--ttl`, default two hours). An expired lock
  is stale and is taken over by the next `acquire`, which reports
  `took_over_stale`. `renew` extends a long run. With `--owner-pid`, a
  dead pid on the same host is also stale. A lock directory with no
  readable owner is a racing starter and is respected.
- **Second run stops, and says so.** `already_running` (exit 3) carries
  the holder record and a `hint` with the `--force` release command. The
  skill prose shows the holder, posts nothing, and states this is not a
  failure of the sweep. Only the maintainer clears a lock by force.
- **Release on both paths.** The block releases after the recap and on
  the existing stop-and-surface path of a failed post, so a failed run
  never leaves the lock held for its lease length. `release --token`
  refuses a non-matching holder; a plain `release` is unconditional;
  `--force` is the operator's override.
- **Read-only stays unlocked.** Classification, state gathering,
  dashboards and briefs take no lock. The block is placed at the write
  step, not at the top of the skill.

## Out of scope

- Locking across skills (a global "one bot run at a time"). Different
  skills post different things.
- Locking read-only skills.
- Retrying a failed write under the lock. A failed post still stops and
  surfaces; the lock only prevents a second concurrent writer.
- The spec-loop runner's own single-flight lock, which guards a working
  tree rather than a forge, and is specified in `spec-loop-runner.md`.

## Acceptance criteria

1. `skill-lock acquire` twice for the same skill and repository: the
   second exits 3 with `status: already_running` and the first holder in
   the result; the lock is unchanged.
2. `acquire` for a different repository or a different skill succeeds
   while the first is held.
3. A lock whose lease has expired, or whose `--owner-pid` is dead on this
   host, is taken over and the result says so; a lock with no owner file
   is reported as `already_running` with `holder: null`.
4. `release --token <wrong>` exits 2 and leaves the lock; `--force`
   releases it; releasing a free lock is a no-op.
5. The lock path for an adopted project is under
   `.apache-magpie-local/run/locks/`; for an unadopted git repository it is
   under `.git/apache-magpie/run/locks/`.
6. On every install, including a marketplace install without the security
   family, `~/.claude/magpie/skill-lock` resolves to a copy of the tool shipped
   in `magpie-vetted-ops`, and the block invokes it through that path.
7. Every batch skill that writes carries the propagated `write-lock`
   block at its write step, rendered with its own skill name, and
   `check-shared-blocks.py` reports no drift.

## Validation

```bash
uv run --directory tools/skill-lock --group dev pytest
uv run --directory tools/skill-lock --group dev ruff check src tests
uv run --directory tools/skill-lock --group dev mypy
uv run --directory tools/setup-preflight --group dev pytest tests/test_layers.py
python3 tools/dev/check-shared-blocks.py
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- The lease default (two hours) is a framework constant, not yet an
  adopter config key. A sweep that legitimately posts for longer must
  call `renew`; the block does not yet say when.
- The lock is advisory for a caller that bypasses the skill prose and
  posts directly with `gh`; a deterministic `agent-guard` check that
  refuses a `gh issue comment` / `gh pr comment` from a batch skill
  without a held lock would make it enforced.
