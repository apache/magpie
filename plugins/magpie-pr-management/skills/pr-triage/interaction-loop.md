<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Interaction loop

This file documents how the skill **presents** proposals to the
maintainer. The classification + action selection (from
`pr-management triage classify`) is
deterministic; this step is where the maintainer's time is
actually spent. Every optimisation here translates directly
into maintainer velocity.

The core idea:

> Present **groups of PRs with the same suggested action**
> together, where each group **spans the entire queue** (every
> page already fetched in Step 1). The maintainer bulk-confirms
> the group, pulls individual PRs out for closer inspection, or
> skips the group.

Every `#NNN` token in the examples below represents output from the
[`pr_link.py`](scripts/pr_link.py) terminal renderer described by
[Golden rule 10](SKILL.md#terminal-pr-reference-renderer). The examples omit
control characters for readability; the live group screen, drill-in view,
action progress / error lines, and summary must never print the literal bare
token.

The underlying `breeze pr auto-triage` tool presented PRs one-
at-a-time (sequential mode) or as a TUI list with per-PR keys.
This skill lands between those: sequential per-group, with a
drill-in for the PRs the maintainer wants to eyeball — except
that each group is **the entire set** of PRs with a given
`(classification, action)` across the queue, not a per-page
slice. A 200-PR full-sweep with 30 passing PRs presents the
maintainer with one `mark-ready` group of 30, not six pages of
five.

---

## Step 3 — Group and present

`triage classify` returns `groups` already keyed by `(classification, action)`, spanning the whole queue and **in presentation order**: workflow approvals first (safety), then the destructive `close` group, then the batchable groups, then the stale sweeps — the riskiest decisions while the maintainer's attention is fresh.
Present them in that order, one at a time; never interleave groups, and if the maintainer quits mid-group, do not start later ones.
Before a group, read the documents in its `docs` list — nothing else is needed to present it.

PRs the table skipped (`skipped`: already triaged, awaiting confirmation, unsettled, inside grace) form no group; mention their count once.

---

## Group presentation

For each group, present one screen of information. The goal is
a decision in under 15 seconds when the suggestion looks right,
or a natural path to per-PR inspection when it doesn't.

Groups can be **large** — a full-queue `mark-ready` group on
an active project might carry 20–40 PRs. Render every PR in
the group (one line per PR) so the maintainer can scan for
outliers; do not silently truncate. If the group exceeds a
terminal-friendly threshold (say, 60 PRs), insert a short
"… N more PRs in this group, showing first 60 …" line at the
bottom of the visible block and require `[E]` to walk past it
(no surprise hidden state behind `[A]ll`).

```text
─────────────────────────────────────────────────────
Group 3 of 8  —  deterministic_flag → draft  —  27 PRs

Common reason: failing CI + unresolved review threads past
the grace window. Spans the entire fetched queue.

  #65401  Add new provider foo                @alice    CI✗ thrd:2  +3/-1  1d
  #65417  Fix parsing of baz                  @bob      CI✗ thrd:1  +12/-4 3h
  #65422  Change caching behavior             @carol    CI✗ thrd:3  +8/-2  2d
  #65460  Typo fix in helm chart              @dave     CI✗ thrd:1  +1/-1  6h
  #65471  Add support for new db dialect      @eve      CI✗ thrd:4  +230/-60 4d
  …  (22 more — full list visible by scrolling up; nothing hidden behind [A])

Suggested action: convert all to draft with violations comment.

  [A]ll   — apply to all 27
  [E]ach  — walk one-by-one
  [P]NN   — pull NN out for inspection (e.g. P65471)
  [O]verride — use a different action for all 27 (comment / close / skip)
  [S]kip  — leave all 27 alone this sweep
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
(see [Batch execution status](#batch-execution-status)).
After `[E]`, the group becomes a queue; each PR gets its own
individual prompt. After `[P]NN`, PR `NN` gets the individual
flow and the rest of the group remains on screen for a follow-
up `[A]`/`[E]`/`[S]`/`[Q]` decision.

The destructive groups — every group whose `batchable` is
false, i.e. `(deterministic_flag, close)` and `(stale_draft, close-stale)` —
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
[3/27] #65471 — step: classify → propose draft
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

### Per-PR progress header

The first line of every individual drill-in must show the PR's stable
position in its group and the pipeline transition currently being presented.
Use a one-based position and the original group size:

```text
[3/27] #65471 — step: classify → propose draft
```

The position is the PR's row index in the group that was presented, not the
number of PRs already handled in the session. Keep it stable throughout the
drill-in and when returning to the group:

- `[E]` uses the current PR's row index in the group.
- `[P]NN` records PR `NN`'s row index before pulling it out; do not renumber
  the remaining group or change the denominator.
- A skipped, pending, or previously pulled-out PR still counts toward the
  original group size.

`classify → propose <action>` means that the classification from Step 2 is
being surfaced together with the suggested action for the maintainer's
decision; it does not trigger a second classification fetch. If the
optimistic-lock check finds that the contributor pushed since Step 1, replace
the marker with `re-classify → propose <action>` after the live state has been
re-evaluated. The subsequent confirmation and mutation are shown by the
per-PR action prompt and batch progress lines, not by changing the saved group
position. If the maintainer overrides the suggested action, update the
`<action>` part of the header before asking for confirmation.

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
| `close-stale` (stale_draft) | `draft`, `skip` |
| `draft` (inactive_open / stale_workflow_approval) | `comment`, `skip` |

`close` from `deterministic_flag` has no override because its
trigger condition (author has >3 flagged PRs) means the
individual violation list varies per PR; a group-level
`comment` override would post wildly different comments with
the same confirmation. Forcing `[E]` keeps the comment
previews per-PR.

---

## Step 4 — Execute

On the maintainer's confirmation, run the group's action file (its `docs` list names it).
Every action re-checks the PR immediately before it mutates — the optimistic lock: the contributor may have pushed while the maintainer was deciding.
The guards (`pr-management triage guard <action>`) refuse on a moved head with `reroute: reclassify`; tell the maintainer *"Contributor pushed a new commit since we classified this PR. Re-classifying…"*, save that PR again with `gql-pr-triage-one`, classify it, and carry on only if the proposed action is unchanged — otherwise drop back to the per-PR drill-in with the new state.

---

## Lazy drill-in fetches

The full-set fetch in Step 1
deliberately omits per-PR deep data (failed-job log snippets,
full diffs, author profile rollups). Defer those to the moment
the maintainer pulls a PR out of a group via `[P]NN`, `[E]`, or
`[W]` on the drill-in screen.

When a per-PR drill-in fires, fetch in the same tool-call turn:

| Drill-in context | Fetch |
|---|---|
| `pending_workflow_approval` group, any PR | `gh pr diff <N>` for the workflow-approval safety review |
| `deterministic_flag → draft/comment` PR | Failed-job log snippets: `gh run view <run_id> --repo <upstream> --log-failed`, the last 40 lines per failed job |
| `close` group (per-PR confirm) | Author's full open-PR list (for the "you have N flagged PRs" line in the body) |
| Any per-PR drill-in pressing `[W]` | Full diff via `gh pr diff <N>`, cached in the session by head SHA |

Cache each lazy fetch in the session cache keyed by `(pr_number,
head_sha)` — re-entering the same drill-in within a session
is a cache hit. There is no prefetching across groups; the
full-set fetch in Step 1 has already paid the upfront cost.

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

## Step 6 — Session summary

On exit (`[Q]`, or after the last group), print the summary the session cache already holds:

```bash
uv run --project <framework>/tools/pr-management pr-management triage session summary --session <scratch>/triage-session.json
```

It prints the per-action / per-reason / pending counts and the throughput as a ready-to-print block; show it as-is.

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
