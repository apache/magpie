<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Interaction loop

This file documents how the skill **presents** proposals to the
maintainer. The classification + action selection (from
[`classify-and-act.md`](classify-and-act.md)) is
deterministic; this step is where the maintainer's time is
actually spent. Every optimisation here translates directly
into maintainer velocity.

The core idea:

> Present **groups of PRs with the same suggested action**
> together. The maintainer bulk-confirms the group, pulls
> individual PRs out for closer inspection, or skips the group.

The underlying `breeze pr auto-triage` tool presented PRs one-
at-a-time (sequential mode) or as a TUI list with per-PR keys.
This skill lands between those: sequential per-group, with a
drill-in for the PRs the maintainer wants to eyeball.

---

## Group ordering

After classification and suggested-action computation, partition
all PRs into groups keyed by `(classification, action)`. Present
the groups in this fixed order:

1. `(pending_workflow_approval, approve-workflow)` — safety-
   relevant; uses the dedicated list-then-select flow in
   [`workflow-approval.md`](workflow-approval.md) instead of the
   generic `[A]/[E]/[P]/[O]/[S]/[Q]` group menu. The standard
   group screen below is bypassed for this group.
2. `(deterministic_flag, close)` — destructive, one-at-a-time
   (but share the same group screen so the maintainer sees the
   "queue pressure" signal from multiple PRs by the same
   author at once).
3. `(stale_copilot_review, draft)` — batchable. Drafts PRs whose
   Copilot review has sat unaddressed for ≥ 7 days.
4. `(deterministic_flag, draft)` — batchable.
5. `(deterministic_flag, comment)` — batchable.
6. `(deterministic_flag, rebase)` — batchable.
7. `(deterministic_flag, rerun)` — batchable.
8. `(deterministic_flag, ping)` — batchable (unresolved threads
   from collaborators).
9. `(stale_review, ping)` — batchable.
10. `(deterministic_flag, request-author-confirmation)` —
    batchable (unresolved threads where the engagement
    heuristic fired; we ask the author whether the PR is
    ready for maintainer review before any label or reviewer
    ping is generated — the first leg of the two-sweep gate).
11. `(author_confirmed_ready, mark-ready)` — batchable
    (presented just before the plain mark-ready group because
    both end with the `ready for maintainer review` label
    going on). The author's reply is shown in the per-PR row
    so the maintainer can read it before confirming `[A]ll` —
    a non-affirmative reply is the maintainer's cue to
    `[P]ick` the PR out and override to `skip` or `ping`.
12. `(passing, mark-ready)` — batchable.
13. `(stale_draft, close)` — batchable but with extra per-PR
    confirm inside the batch (these are rarely wrong but when
    wrong they're very wrong).
14. `(inactive_open, draft)` — batchable.
15. `(stale_workflow_approval, draft)` — batchable.

Skipped (filtered before group presentation) but worth noting
for completeness: `awaiting_author_confirmation` PRs (we asked
the author, they have not yet replied, and we are still inside
the cooldown) classify as `skip` in
[row 14b](classify-and-act.md#decision-table) and never form
a group. They reappear once the author replies (→ group 11) or
when the cooldown lapses (→ Sweep 5 in
[`stale-sweeps.md`](stale-sweeps.md)).

The ordering is chosen so the maintainer always faces the
riskiest decisions first, while their attention is fresh. The
last few groups (stale sweeps) are mostly auto-apply-all.

Never interleave groups. Finish one before starting the next.
If the maintainer quits mid-group, don't start later groups.

---

## Group presentation

For each group, present one screen of information. The goal is
a decision in under 15 seconds when the suggestion looks right,
or a natural path to per-PR inspection when it doesn't.

```text
─────────────────────────────────────────────────────
Group 3 of 8  —  deterministic_flag → draft  —  5 PRs

Common reason: all have failing CI + unresolved review threads
past the grace window.

  #65401  Add new provider foo                @alice    CI✗ thrd:2  +3/-1  1d
  #65417  Fix parsing of baz                  @bob      CI✗ thrd:1  +12/-4 3h
  #65422  Change caching behavior             @carol    CI✗ thrd:3  +8/-2  2d
  #65460  Typo fix in helm chart              @dave     CI✗ thrd:1  +1/-1  6h
  #65471  Add support for new db dialect      @eve      CI✗ thrd:4  +230/-60 4d

Suggested action: convert all to draft with violations comment.

  [A]ll   — apply to all 5
  [E]ach  — walk one-by-one
  [P]NN   — pull NN out for inspection (e.g. P65471)
  [O]verride — use a different action for all 5 (comment / close / skip)
  [S]kip  — leave all 5 alone this sweep
  [Q]uit  — exit session
```

### Columns explained

| Column | Content |
|---|---|
| PR # | number, clickable link to the PR |
| Title | truncated to fit, full title on per-PR expand |
| Author | login, clickable link to GitHub profile |
| CI | `CI✓` passed, `CI✗` failed, `CI?` unknown / empty |
| thrd | unresolved-thread count |
| +/- | additions / deletions from the PR record |
| Age | human-readable "time since last update" |

Optional columns when relevant: `beh:NNN` for commits-behind,
`draft` marker, `flagged:N` for the author's overall flagged-
PR count (shown only when > 3, driving the `close` suggestion).

Keep the row to **one line** per PR. Anything longer makes the
group screen itself a decision bottleneck.

---

## Decision keys

| Key | Action |
|---|---|
| `[A]` | Apply the suggested action to every PR in the group. |
| `[E]` | Walk through the group one PR at a time, per-PR confirm each. |
| `[P]NN` | Pull PR `NN` out of the group into an individual drill-in; the rest of the group remains pending. |
| `[O]` | Override the action for the whole group to a different verb (offered list is the safe-overrides set for this group — see [`#group-action-override`](#group-action-override)). |
| `[S]` | Skip the group — no mutations, all members marked "skipped" in the session. |
| `[Q]` | Quit the session. Emit summary. |

After `[A]` the action is executed for every PR in the group
(see batching rules in [`actions.md#batching-execution`](actions.md)).
After `[E]`, the group becomes a queue; each PR gets its own
individual prompt. After `[P]NN`, PR `NN` gets the individual
flow and the rest of the group remains on screen for a follow-
up `[A]`/`[E]`/`[S]`/`[Q]` decision.

The two destructive groups —
`(deterministic_flag, close)` and `(stale_draft, close)` —
require a per-PR confirm inside `[A]`/`[E]` alike. `[A]` on
those means "don't drop me back to the group menu between
PRs", not "apply without confirm".

`(pending_workflow_approval, *)` does not use the standard
group menu at all — see
[`workflow-approval.md`](workflow-approval.md) for its
list-then-select flow, which has its own selection-and-confirm
step in place of `[A]`/`[E]`.

---

## Individual (drill-in) presentation

When a PR is pulled out of a group (via `[P]`, `[E]`, or
because its group mandates per-PR), present the full detail:

```text
─────────────────────────────────────────────────────
PR #65471   "Add support for new db dialect"
Author: @eve  (tier: new, 2 merged / 5 total on this repo)
Age: opened 4d ago, last push 6h ago
Branch: eve-fork:feature/dialect → apache:main (230 / -60, 12 behind)
Labels: area:providers, provider:postgres

CI: FAILURE (4 failed checks)
  - Tests (postgres)                   ← known recent main-branch flake
  - Tests (sqlite)
  - Static checks
  - mypy-providers                     ← only-static-check pattern broken

Unresolved review threads: 4
  - @alice (MEMBER): "Why does this touch src/core/..."
  - @uranusjr (MEMBER): "Consider using the existing hook abstraction"
  - @eladkal (MEMBER): "Should we add a newsfragment?"
  - @potiuk (MEMBER): "Typo on line 74"

Suggested: draft — "Has quality issues across all three signals"

[Draft comment body preview — click to expand]

Decide:
  [D]raft  [C]omment  [Z]lose  [R]ebase  [F]rerun  [M]ark ready
  [B]ack to group  [S]kip  [O]pen in browser  [W]show full diff
```

The action keys on the per-PR screen are the **full** verb
menu, not restricted to the group's suggested action. The
maintainer can override per-PR to any valid action.

`[W]` fetches and displays the full diff (via
`gh pr diff <N>` — cache in session cache keyed by head SHA).
This is the only moment a diff is read for a non-workflow-
approval PR, and it's gated on the maintainer asking for it.

`[B]` returns to the group screen with PR `NN` marked as
"pulled-out-and-left-pending". The maintainer can come back
to it after finishing the rest of the group.

---

## Group action override

`[O]` on a group prompts the maintainer with a short list of
safe alternatives:

| Group's suggested action | Safe overrides |
|---|---|
| `draft` | `comment`, `rebase`, `skip` |
| `comment` | `draft`, `rebase`, `skip` |
| `rebase` | `comment`, `skip` |
| `rerun` | `comment`, `skip` |
| `mark-ready` | `skip` |
| `request-author-confirmation` | `ping` (skip the author-confirmation step and post the plain reviewer-ping body directly if the maintainer thinks the engagement heuristic over-reached), `skip` |
| `ping` | `comment`, `skip` |
| `close` (deterministic_flag) | — (no overrides — use `[E]` to downgrade individually) |
| `close` (stale_draft) | `draft`, `skip` |
| `draft` (inactive_open / stale_workflow_approval) | `comment`, `skip` |

`close` from `deterministic_flag` has no override because its
trigger condition (author has >3 flagged PRs) means the
individual violation list varies per PR; a group-level
`comment` override would post wildly different comments with
the same confirmation. Forcing `[E]` keeps the comment
previews per-PR.

---

## Optimistic lock (re-check before mutate)

Between the fetch (Step 1 / 2) and the mutation (Step 4) the
contributor may have pushed a new commit. Before executing any
action for a given PR, re-check the PR's `head_sha` against
the one captured at fetch time:

```bash
gh api graphql -F owner=<owner> -F repo=<repo> -F number=<N> -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) {
        headRefOid
        mergeable
        statusCheckRollup: commits(last: 1) {
          nodes { commit { oid statusCheckRollup { state } } }
        }
      }
    }
  }'
```

If `headRefOid` matches, proceed. If it differs:

- Tell the maintainer: *"Contributor pushed a new commit since
  we classified this PR. Re-classifying…"*.
- Re-fetch the full PR record and re-classify.
- If the new classification yields the **same** suggested
  action, carry on.
- If it differs, drop back to the per-PR drill-in with the new
  state and let the maintainer re-decide.

This guard catches the common race and prevents the worst
failure mode ("convert-to-draft-on-a-commit-that-wasn't-broken").
Burn the one extra GraphQL point per action — a bad mutation
costs more.

Batch the re-check queries for `[A]` actions — one aliased
`pullRequest(number: N)` per PR in the group, one round-trip.

---

## Prefetch plan

Whenever a group is presented to the maintainer (an
information-only turn), fire **in the same turn** any follow-up
fetches the next decision will need. Parallel tool calls make
this free — the network round-trip overlaps with the
maintainer's reading time.

Concrete prefetches:

| Currently showing | Prefetch |
|---|---|
| Any group | Next page's PR-list + rollup query (if `has_next_page` and `page_num < max_num / 50`), then **pre-classify and pre-render the first group** of that page — see [`#pre-classification-and-pre-rendering-of-the-next-page`](#pre-classification-and-pre-rendering-of-the-next-page) below |
| `pending_workflow_approval` group | `gh pr diff <N>` for the first 2 PRs in the group |
| `deterministic_flag → draft/comment` group, one PR at a time | Failed-job log snippets for the current PR and the next PR in the queue |
| `close` group (per-PR) | Author's full open-PR list (for the "you have N flagged PRs" line in the body) |
| Any per-PR drill-in | Author profile (account age, repo merge rate) if not already cached |

Do **not** prefetch:

- Data for groups the maintainer may not reach this session
  (page 3 when they're on page 1).
- Full diffs for non-workflow-approval PRs unless the
  maintainer actually presses `[W]`.
- Author profiles for PRs in stale-sweep groups — they're being
  closed or drafted with minimal per-PR custom data, so the
  profile costs more than it saves.

When a prefetched result lands before the maintainer acts, store
it in the session cache; when the maintainer eventually triggers
the drill-in, it's instant.

### Pre-classification and pre-rendering of the next page

The next-page prefetch is most valuable when it carries the page
all the way through to a presentable form, not just to raw
GraphQL nodes. Classification is a pure function over the
fetched data (no further GraphQL, no prompts — see
[`classify-and-act.md`](classify-and-act.md)), and so is the
group-screen template ([`#group-presentation`](#group-presentation));
both can run eagerly the moment the prefetch resolves. Pipeline:

1. **Turn N** (presenting page N's current group): fire the
   page-(N+1) GraphQL call in parallel with the group screen,
   as the table above documents.
2. **Turn N+1** (or whenever the prefetch resolves, before the
   maintainer's decision lands): apply pre-filters F1–F5b, walk
   the decision table top-to-bottom, run the Real-CI guard, and
   group the resulting `(pr, classification, action, reason)`
   tuples — exactly as Steps 2 and 3 of [`SKILL.md`](SKILL.md)
   would have done synchronously at page-turn time. Build the
   first group's screen text from the
   [group-presentation template](#group-presentation). Stash
   the bundle under `prefetched_pages.<page_num>` in the
   session cache — see
   [`fetch-and-batch.md#session-cache`](fetch-and-batch.md#session-cache)
   for the schema.
3. **Page-turn moment** (current page exhausted): instead of
   re-fetching and re-classifying, read the prefetched bundle
   and present the first group immediately. The maintainer
   sees zero classification latency at the page boundary. See
   [`SKILL.md#step-5--paginate-and-sweep`](SKILL.md#step-5--paginate-and-sweep).

Invalidation: if the optimistic-lock re-check at execute time
(see [`#optimistic-lock-re-check-before-mutate`](#optimistic-lock-re-check-before-mutate))
finds a head-SHA mismatch for a PR in the prefetched bundle,
drop that PR's tuple and re-classify it inline. The bundle as
a whole survives — a single stale PR does not poison the page.

If the maintainer quits (`[Q]`) on the current page, the
prefetched bundle is discarded on session exit. The work was
wasted, but the GraphQL cost was the same one query that would
have happened at the page-turn anyway — the downside is
small. Skip the pre-classification (not just the prefetch) only
when the prefetch itself was skipped per the "last page or no
larger pending work" heuristic in
[`fetch-and-batch.md#prefetch-plan`](fetch-and-batch.md#prefetch-plan).

---

## Batch execution status

When `[A]` triggers batched mutations, show live progress as a
short table that updates in-place:

```text
Applying action: draft  (5 PRs, parallelism: 5)

  #65401 @alice — posting comment… done
  #65417 @bob   — converting to draft… done
  #65422 @carol — posting comment… failed (PR already closed)
  #65460 @dave  — converting to draft… done
  #65471 @eve   — converting to draft… done  (head SHA changed, re-classified — same action, proceeding)

4 succeeded, 1 skipped. Continue to next group? [Y/q]
```

Failures in a batch don't cascade-abort. The per-PR error is
logged, the batch continues, and the final tally is surfaced
before moving on.

---

## Session summary

On exit (either `[Q]` or after the last group), print a
session summary:

```text
Session summary — 2026-04-22 09:42 UTC → 10:07 UTC (25m)

PRs presented:  47
PRs acted on:    22
  - drafted:           5
  - commented:         3
  - closed:            2
  - rebased:           4
  - reruns triggered:  3
  - marked ready:      3
  - author-confirm requests:  1
  - pings posted:      2
PRs skipped:     15   (12 already triaged / inside grace, 2 bot, 1 collaborator)
PRs left pending: 10   (reached [Q] before classifying)

Throughput: 22 actions / 25m = 53 PRs/h
```

Write a copy to the session cache under a `last_summary`
key — re-invocations of the skill can reference it with *"last
triage run closed 2h ago, these 12 PRs were skipped then"*.
Don't persist across sessions on disk beyond the cache.

---

## Failure mode: the maintainer disagrees with every suggestion

If the first two groups the maintainer touches are
entirely `[O]`-overridden or `[S]`-skipped, the suggestions
logic is miscalibrated for this session (or a systemic CI
issue has landed). Surface a one-line note:

> Heads-up: the first two groups were overridden. If main-
> branch CI is broken this session, the `rerun` and `rebase`
> suggestions will be noisy. Would you like to skip to the
> stale sweeps? [Y/n]

This is a cheap safety valve against the skill burning through
a frustrated maintainer's morning on stale suggestions. It only
fires once per session and only if the override rate is
high — don't be annoying.
