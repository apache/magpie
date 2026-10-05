<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Backport check (Step 0.7)

Projects that maintain release branches by cherry-picking from the
default branch receive a steady stream of backport PRs, usually
opened by a bot. Those PRs are dropped by pre-filters F1/F2 (bot or
collaborator author), yet they carry the two decisions a release
branch most needs made: *is this exactly what landed on the default
branch?* and *is it allowed on a release branch at all?* This step
answers both, early, before the main triage flow.

**Runs only when `backport_branches` is set** in
[`<project-config>/pr-management-config.md`](../../../magpie-setup/templates/pr-management-config.md#workflow-choices).
When it is empty (the default), skip this step entirely — the
project does not cherry-pick.

## Scope

Every open PR whose `baseRefName` matches a `backport_branches`
pattern, **regardless of author** (F1/F2 do not apply here) and
regardless of draft state. PRs matched here are reported in their
own group and are not fed into Step 2 again.

## 1 — Resolve the source commit

For each PR commit, find the default-branch commit it was taken
from, in this order:

1. a `(cherry picked from commit <sha>)` trailer in the commit
   message;
2. the source PR number in the title (e.g. `... (#NNN)`), resolved
   to its merge commit on the default branch.

Confirm the commit is an ancestor of the default branch. If no
source can be resolved for a commit, classify the PR
`backport_unverified` and stop.

## 2 — Is it a direct cherry-pick?

This needs a local clone with the default branch, the base branch,
and `pull/<N>/head` fetched. For each PR commit, run
`git cherry <base> <pr-head>`:

- commits marked `-` already have an equivalent on the base branch
  and are ignored; if **every** commit is `-`, classify
  `backport_already_landed`;
- for each remaining commit, compare
  `git show -U0 <commit> | git patch-id --stable` with the same for
  its source commit.

Use `-U0` on both sides: a release branch's surrounding lines
differ from the default branch's, so a patch-id with context
reports faithful cherry-picks as modified. All remaining commits
match → `direct_cherry_pick`. Any mismatch →
`adapted_backport`; show the maintainer the `+`/`-` lines that
differ, since an adaptation is exactly where a backport goes
wrong.

## 3 — Is it allowed on a release branch?

With `backport_policy: fixes-only` (the default), classify the
**source** change, reading the source PR's labels, title, body and
changed files — not the backport's, which only repeats the title:

- **fix** — corrects wrong behaviour (a crash, a hang, a wrong
  result, a broken build or tool);
- **not a fix** — a new feature or new check, a behaviour change
  (new validation that rejects what was accepted), a new
  deprecation, a removal of something importable or public, or a
  refactor/cleanup.

A release note or changelog entry marking the change as
significant, breaking or a deprecation is a strong "not a fix"
signal. When the signals conflict, say so and let the maintainer
decide — never guess towards "fix". A "not a fix" PR is classified
`backport_policy_violation`. With `backport_policy: any`, skip this
sub-step.

## Classifications and proposed actions

| Classification | Proposed action |
|---|---|
| `direct_cherry_pick` (and a fix) | hand off for review/merge — mark ready if draft; never merge from triage ([golden rule 5](SKILL.md#golden-rules)) |
| `adapted_backport` | surface the differing lines for a maintainer review |
| `backport_policy_violation` | propose `close`, with the reason (feature, behaviour change, deprecation, removal, refactor) |
| `backport_already_landed` | propose `close` — name the base-branch commit that already carries the change |
| `backport_unverified` | surface for a maintainer — no source commit could be found |

Every action is a proposal the maintainer confirms (golden rule 1).
