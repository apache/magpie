<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Stale sweeps

The stale-sweep phase runs after the interactive triage is
done (Step 5 in [`SKILL.md`](SKILL.md)). Its job is to clear
four categories of PRs that have gone silent:

1. **Stale drafts** — drafts that haven't moved in weeks; either
   triaged and ghosted, or never triaged and drifted.
2. **Inactive open PRs** — non-draft PRs that have sat open
   for over 4 weeks with no activity.
3. **Stale workflow-approval PRs** — first-time-contributor
   PRs awaiting workflow approval that have sat for over 4
   weeks without the author pushing new commits.
4. **Stale author-confirm-requests** — PRs where the bot asked
   the author to confirm readiness for maintainer review (the
   first leg of the [row 14c](classify-and-act.md#decision-table)
   two-sweep flow) and the author has been silent past the
   cooldown.

Each category has deterministic trigger criteria, a fixed
action, and a canned comment. They are surfaced through the
same group-presentation machinery as regular triage (see
[`interaction-loop.md`](interaction-loop.md)) — the maintainer
confirms per group before anything is mutated.

The sweep is opt-in for full runs (`triage` selector) and
mandatory for `stale` runs (which skip the interactive triage
entirely). Both paths go through the same rules below.

---

## Inputs

Each stale sweep needs these timestamps per PR:

- `updated_at` — the PR's `updatedAt` field (already in the
  batch query)
- `last_triage_comment_at` — the `createdAt` of the most
  recent comment by the viewer containing the
  `Pull Request quality criteria` marker, if any
- `last_author_activity_at` — the max of three timestamps,
  all already in the batch query:
  1. the head commit's `committedDate` from `commits(last: 1)`
     (catches pushes, including force-pushes — `committedDate`
     advances on rebase even when no new code is added),
  2. the `createdAt` of the most recent **issue-level** comment
     by the PR author in `comments(last: 10)`,
  3. the `createdAt` of the most recent **review-thread** reply
     by the PR author across
     `reviewThreads.nodes.comments(first: 5)` (filter
     `author.login == pullRequest.author.login`).
  Item 3 matters because line-level discussion is the most
  common form of author response on substantive PRs; omitting
  it would surface PRs as stale even while an active inline
  conversation is in progress.
- `last_maintainer_comment_at` — the `createdAt` of the most
  recent comment in `comments(last: 10)` whose
  `authorAssociation` is one of `COLLABORATOR`/`MEMBER`/`OWNER`,
  excluding the viewer's own triage comments (the
  `Pull Request quality criteria` marker disqualifies).

All inputs come from the same aliased query that drives
classification — no extra fetches. If a PR hasn't been triaged
in the current session and also wasn't triaged in a prior one,
`last_triage_comment_at` is null and Sweeps 1a/1b fall back to
`updated_at` alone.

`<now>` is the session start time (captured in UTC on entry).
Use a single reference moment for the whole sweep so edge
cases (a PR updated mid-session) don't shift.

---

## Sweep 1 — Stale drafts

Two sub-cases, both resulting in `close`:

### 1a. Triaged draft with no author reply ≥ 7 days

**Trigger.**

- `isDraft == true`
- `last_triage_comment_at` is not null
- `<now> - last_triage_comment_at >= 7 days`
- No comment by the author after `last_triage_comment_at`

**Action.** `close` — post the
[stale-draft-close](comment-templates.md#stale-draft-close) comment,
then close. No label (these are not quality-violation closes).

**Reason string.** *"Draft triaged N days ago, no author reply — close with stale-draft notice"*.

### 1b. Untriaged draft with no activity ≥ 2 weeks

**Trigger.**

- `isDraft == true`
- `last_triage_comment_at` is null
- `<now> - updated_at >= 14 days`

**Action.** `close` — post the "untriaged-draft" variant of
[stale-draft-close](comment-templates.md#stale-draft-close), then
close. No label.

**Reason string.** *"Draft inactive for W weeks — close with stale-draft notice"*.

### Group behaviour

Stale-draft closes are **batchable but with per-PR confirm
inside the batch** — the same rule as the
`deterministic_flag → close` group. `[A]ll` walks the list
without re-prompting at the group level, but each PR still
flashes its comment preview and waits for `Y` / `n` before
mutating. See [`interaction-loop.md#decision-keys`](interaction-loop.md).

---

## Sweep 2 — Inactive open PRs

**Trigger.**

- `isDraft == false`
- `<now> - updated_at >= 28 days`
- No other stale classification applies

**Action.** `draft` — convert to draft and post the
[inactive-to-draft](comment-templates.md#inactive-to-draft)
comment. No label.

**Reason string.** *"Open non-draft inactive for W weeks — convert to draft"*.

### Rationale

Closing an inactive *open* PR is more disruptive than closing a
draft (the author actively asked for review at some point).
Converting to draft is the softer equivalent — it stops
blocking the queue, preserves the discussion, and the author
can mark as ready again when they resume.

### Group behaviour

Batchable with simple `[A]ll` (no per-PR confirm inside the
batch). The action is recoverable — the author can revert with
one click — so the looser batching is appropriate.

---

## Sweep 3 — Stale workflow-approval PRs

**Trigger.**

- Classification was `pending_workflow_approval` at fetch time
- `<now> - updated_at >= 28 days`
- PR author has not pushed since (i.e. `head_sha` is the same
  as at last update)

**Action.** `draft` — convert to draft and post the
[stale-workflow-approval](comment-templates.md#stale-workflow-approval)
comment. No label.

**Reason string.** *"Awaiting workflow approval for W weeks, no activity — convert to draft"*.

### Rationale

A first-time-contributor PR that sits waiting for approval for
a month usually means the contributor abandoned the attempt.
Closing feels harsh given they never even got CI feedback;
drafting clears the queue and leaves them the option to
resume.

### Group behaviour

Same as Sweep 2 — simple `[A]ll`.

---

## Sweep 4 — Stale ready-for-review label

When a PR carries `ready for maintainer review` and the author
has been silent for ≥ 7 days after a maintainer comment, branch
health splits the disposition: 4a strips the label; 4b proposes
`close`.

### Why a separate sub-query

The default fetch search (see
[`fetch-and-batch.md#search-query-construction`](fetch-and-batch.md#search-query-construction))
excludes `ready for maintainer review`, so candidates here are
never in the default page. Sweep 4 issues its own paged search
on the same enrichment schema — no new GraphQL surface:

```text
is:pr is:open repo:<upstream>
label:"ready for maintainer review"
sort:updated-asc
```

The label name comes from
[`<project-config>/pr-management-config.md → ready_for_maintainer_review_label`](../../../projects/_template/pr-management-config.md)
— do not hard-code the string.

### Common trigger (4a and 4b)

- The PR carries the `ready for maintainer review` label.
- The `ready for maintainer review` label was added ≥ 7 days ago
  (`<now> - ready_label_added_at >= 7 days`, where
  `ready_label_added_at` is the most recent
  `LabeledEvent { label.name == "ready for maintainer review" }`
  timestamp from the PR's `timelineItems`).
- The most recent maintainer comment came **after** the label
  was added (`last_maintainer_comment_at > ready_label_added_at`)
  AND `<now> - last_maintainer_comment_at >= 7 days`.
- `last_author_activity_at` is null **or**
  `last_author_activity_at <= last_maintainer_comment_at`.

The "maintainer comment after label-add" condition is the
load-bearing guard against the freshly-promoted misfire: when a
maintainer just added the `ready for maintainer review` label,
the queue moves to the maintainers, not the author. A pre-label
maintainer comment is part of the conversation that *got* the PR
to ready; counting it as proof of author silence would close PRs
the moment they get promoted, which is the opposite of what
`ready for maintainer review` means. This guard mirrors the
"after the label-add timestamp" pattern row F4 already uses for
regression detection (see
[`classify-and-act.md#decision-table`](classify-and-act.md), F4
row).

The author-activity condition makes this sweep about *author
silence*, not label age — a "still working on it" reply resets
the clock.

### Branch-health resolution — re-poll mergeability live (before 4a/4b)

The 4a/4b split turns on whether the branch is *healthy* or *rotted*. **Do not
read that from the batched `mergeable` / `mergeStateStatus`.** GitHub computes
mergeability lazily, so a batched search over the `ready` queue returns
`UNKNOWN` for many PRs and `BLOCKED` for *most* (branch protection withholding
the merge pending the required approval they do not have yet) — gating the split
on the batch value mis-routes clean-but-unapproved stale PRs into 4b (close) when
their branch is actually fine. The Sweep-4 candidate set is already small (stale
ready PRs concentrate at the back of the queue), so resolve mergeability **live,
per candidate**:

```bash
gh api repos/<upstream>/pulls/<N> --jq '[.mergeable, .mergeable_state]|@tsv'
```

Classify the live `(mergeable, mergeable_state)` pair:

- `mergeable == true` and `mergeable_state ∈ {clean, has_hooks, unstable, behind, blocked}` → **healthy** (`blocked` is a clean branch withheld only on the missing approval — not bitrot) → route to **4a**.
- `mergeable == false` **or** `mergeable_state == dirty` → **conflicted** → route to **4b**.
- `mergeable == null` / `mergeable_state == unknown` after the live call → **defer this run** (do not strip, do not close); it settles and re-qualifies next sweep.

`statusCheckRollup.state == FAILURE` independently routes to **4b** (red CI is
bitrot regardless of mergeability). This mirrors the live re-poll the
[`pr-management-quick-merge`](../pr-management-quick-merge/candidate-rules.md#stage-3--live-merge-readiness)
skill uses for the same reason — observed: a batch mergeability gate misjudged
~87% of a real `ready` queue.

### 4a — Branch healthy → strip label

**Extra trigger.** The live branch-health resolution above classifies the PR as
**healthy** (not conflicted, and `statusCheckRollup.state != FAILURE`). A batch
`mergeStateStatus == BLOCKED` is *healthy* here, not a reason to skip 4a.

**Action.** `strip-ready-label`. See
[`actions.md#strip-ready-label`](actions.md#strip-ready-label--remove-the-ready-for-review-label-no-comment).

**Reason string.** *"Ready-for-review label stale — N days
since maintainer comment, no author reply, branch healthy —
strip label only"*.

**Group behaviour.** Simple `[A]ll` — non-destructive, no
per-PR confirm.

### 4b — Branch rotted → propose close

**Extra trigger.** The live branch-health resolution above classifies the PR as
**conflicted** (`mergeable == false` / `mergeable_state == dirty`) **or**
`statusCheckRollup.state == FAILURE`. A batch `mergeStateStatus == BLOCKED` is
**not** a 4b trigger — that is the healthy-awaiting-approval case (4a).

**Action.** `close` with the
[`stale-ready-label-close`](comment-templates.md#stale-ready-label-close)
comment template; **skip the quality-violations label step**
(close reason is bitrot, not policy violation). Otherwise
[`actions.md#close`](actions.md#close--close-with-comment-and-quality-violations-label)
unchanged.

**Reason string.** *"Ready-for-review label stale — N days
since maintainer comment, no author reply, branch has
<bitrot_signal> — close"*. `<bitrot_signal>` ∈ {`failing CI`,
`merge conflicts`, `failing CI + conflicts`}.

**Group behaviour.** Per-PR confirm inside the batch
(inherited from the `close`-group rule, SKILL.md Step 3).

---

## Sweep 5 — Stale author-confirm-request

When a PR has a pending author-confirmation request from a
prior sweep (the first leg of the
[row 14c](classify-and-act.md#decision-table) two-sweep flow)
and the author has not replied within the cooldown, this sweep
proposes a fallback action so the PR does not sit indefinitely
in the "asked, awaiting reply" limbo state.

### Trigger

- [`viewer_confirmation_request_present`](classify-and-act.md#viewer_confirmation_request_present)
  is true (we posted the request, the head SHA has not advanced
  since).
- [`pending_author_confirmation`](classify-and-act.md#pending_author_confirmation)
  is true (no author reply after our request).
- `<now> - confirmation_request_at >= 7 days`, where
  `confirmation_request_at` is the `createdAt` of the viewer's
  most recent comment carrying the
  `ready for maintainer review confirmation` marker.

The same 7-day window used by
[Sweep 4](#sweep-4--stale-ready-for-review-label) applies here
— the symmetry is intentional: in both cases the author has
gone silent after we asked them for input on a PR they own.

### Action

`ping` with the
[`reviewer-ping` author-primary body](comment-templates.md#reviewer-ping)
(unresolved threads from collaborators). The new ping makes
the unresolved-thread state itself the topic again — the
confirmation request was a softer ask that did not work, so
the next sweep escalates to the normal unresolved-thread nudge.

Do **not** strip the prior confirmation-request comment — it
remains as part of the PR history, and a contributor returning
later can see both pings in order.

**Reason string.** *"Author confirmation requested N days ago,
no reply — escalating to plain reviewer ping"*.

### Group behaviour

Batchable with simple `[A]ll` — the action is a single
non-destructive comment, recoverable by the maintainer if it
fires on the wrong PR.

### Why not `close` or `draft`?

`close` would punish a contributor whose only "fault" is
missing a confirmation question; `draft` would lose the PR's
review-ready posture even though every other signal
(CI green, no conflicts) is healthy. Plain `ping` is the
minimum escalation that re-surfaces the PR to the original
reviewer pool without prejudging where the responsibility
lies.

### Override

If the maintainer reading the proposal sees the unresolved
threads are obviously addressed (e.g. the author engaged
substantively in-thread but never replied to our
confirmation), they can `[O]`-override the group to
`mark-ready` — that path skips the ping entirely and just
applies the label, treating the author's earlier in-thread
engagement as the implicit confirmation. The override is
deliberately not the default because a programmatic test for
"engagement was substantive" would re-introduce exactly the
false-positive risk the two-sweep gate was designed to
eliminate.

---

## Order of sweeps

1. Sweep 1a (triaged drafts, 7d)
2. Sweep 1b (untriaged drafts, 2w)
3. Sweep 2 (inactive open, 4w)
4. Sweep 3 (stale WF approval, 4w)
5. Sweep 4a (stale ready-label, healthy, 7d) → strip
6. Sweep 4b (stale ready-label, rotted, 7d) → close
7. Sweep 5 (stale author-confirm-request, 7d) → ping

Run 1a before 1b so a draft that's both "triaged 7d ago" and
"never-triaged 2w ago" (the triage comment is recent but the
overall PR is old) is categorised by the more precise trigger.
In practice that overlap is rare, but the order is defined.

Sweep 4 operates on a disjoint candidate set (the labeled PRs
the default search excluded), so there is no overlap with the
earlier sweeps. 4a runs before 4b so the cheap label-tidying
batch lands before the per-PR-confirm `close` group.

Sweep 5 runs last because its candidate set is also disjoint
from the earlier sweeps — PRs holding a confirmation-request
comment do not carry the `ready for maintainer review` label
yet (the label is the second-leg outcome), and their author
silence is more recent than the 4-week thresholds in Sweeps 2
and 3.

---

## What the sweeps do NOT do

- **No force-close for "PR has merge conflicts for N weeks".**
  Merge-conflict staleness is still the author's to fix; we
  close via draft-then-stale-draft-close, not directly.
- **No automatic reopen.** If a sweep closes a PR by mistake,
  the maintainer reopens it manually — the skill never
  reverses its own mutation without a fresh confirmation.
- **No cross-author batching.** The `flag-suspicious` action
  from [`workflow-approval.md`](workflow-approval.md) *does*
  close multiple PRs per author, but it's a separate flow with
  its own safety protocol; the stale sweeps never extend their
  scope beyond "this one PR meets the criteria, close this one
  PR".
- **No sweeping across repos.** Each sweep runs against a
  single `<repo>`. Running the skill against a different repo
  is a separate session with its own cache.

---

## Budget

The sweeps add no new GraphQL calls beyond what classification
already fetched — the timestamps (`updated_at`,
`last_triage_comment_at`) come from the per-page batch query.
The one exception is Sweep 4's
[live mergeability re-poll](#branch-health-resolution--re-poll-mergeability-live-before-4a4b):
one `GET /pulls/<N>` REST call per *stale Sweep-4 candidate* (a
small set — single digits in a typical sweep), the unavoidable
cost of getting a trustworthy branch-health read. Beyond that,
the only cost is mutations for each confirmed action — which is
the whole point of the sweep.

A typical morning `<upstream>` sweep surfaces:

- 1–3 triaged drafts hitting the 7-day mark
- 2–5 untriaged drafts hitting the 2-week mark
- 1–3 inactive open PRs
- 0–2 stale workflow-approval PRs

…which is 4–13 mutations total, well under the rate-limit
budget. If a sweep turns up more than 50 candidates, something
is off (a previous sweep was never run; a release freeze
piled up activity) — surface the count and ask the maintainer
whether to continue, don't blast through silently.

---

## Dry-run

With `dry-run` on, every sweep displays its candidate group but
refuses to execute `[A]` or per-PR confirm — the maintainer
sees exactly what *would* happen without mutating anything.
Useful for calibrating the thresholds (if a sweep surfaces a
PR you think shouldn't be stale, you need to change the
timestamps-for-activity calculation, not the thresholds).

The session summary still reports the counts, tagged
`(dry-run — not mutated)`.
