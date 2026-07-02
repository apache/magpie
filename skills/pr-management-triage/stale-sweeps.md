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
- `last_triage_comment_at` — the most recent triage-marker
  timestamp from **either feedback channel**, if any: the
  `createdAt` of the most recent viewer comment containing the
  `Pull Request quality criteria` marker (comment channel), OR
  the `triaged=` timestamp parsed from the `pr-triage-fold` block
  in the PR `body` (pr-body channel — the default; see
  [`viewer_triage_fold_present`](classify-and-act.md#viewer_triage_fold_present)).
  When both are present (a project that switched channels), take
  the later of the two. Despite the legacy field name, this is
  "last triaged at", not strictly a comment.
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

## Maintainer-court guard (applies to every sweep)

A PR satisfying
[`author_question_to_maintainer_unanswered`](classify-and-act.md#author_question_to_maintainer_unanswered)
— the author's most recent comment `@`-mentions a maintainer (or
the committers team) and no maintainer has replied since — is in
the **maintainers' court**: the next move is a maintainer
answering, not anything the author owes. Every sweep below honours
it:

- **Sweeps 1–3** (close / convert-to-draft for staleness) **skip
  it.** A PR is not "abandoned by the author" while the author is
  waiting on *us*; closing or drafting it for inactivity punishes
  the contributor for maintainer silence. This is the exact
  failure that closed a real PR after the triage process missed an
  open question to the team.
- **Sweep 4** keeps the `ready for maintainer review` label (see
  [Step B](#step-b--court-disposition)) — the label *means* "ball
  in the maintainers' court", which is precisely true here.

Inactivity timers (`updated_at`-based) do **not** override this
guard; only a maintainer reply — which flips the PR out of the
precondition — does. The guard is the stale-sweep counterpart of
pre-filter [F5c](classify-and-act.md#pre-filters), which removes
the same PRs from the *interactive* flow.

---

## Ready-label exclusion (applies to Sweeps 1–3)

PRs carrying the `ready for maintainer review` label are the
**exclusive domain of [Sweep 4](#sweep-4--stale-ready-for-review-label)**
(court disposition). Sweeps 1, 2, and 3 must **never** touch a
ready-labelled PR — never close it, convert it to draft, assign its
author, or fold a triage note into it.

Two enforcement points, **both mandatory**:

1. **Candidate query.** Every standalone candidate search a sweep
   issues MUST carry the negative label filter
   `-label:"ready for maintainer review"`, exactly as the default
   sweep search shape already does (see
   [`fetch-and-batch.md`](fetch-and-batch.md#the-one-query-that-matters--pr-list--rollup-enrichment),
   where the default shape carries `-label:"ready for maintainer review"`
   and Sweep 4 is the sole exception that flips it to a positive
   match). A sweep that **builds its own query** — e.g. Sweep 2's
   `is:pr is:open draft:false updated:<DATE>` — is the danger case: the
   exclusion is easy to drop when the query is hand-written rather than
   inherited from the default shape. State it explicitly in every
   sweep's trigger below and never omit it.
2. **Per-PR pre-mutation guard.** Immediately before executing **any**
   Sweep 1/2/3 mutation, re-confirm the target PR does **not** carry
   the `ready for maintainer review` label (it may have been added
   between the candidate fetch and the mutation). If it does, drop the
   PR from the sweep — Sweep 4 owns it.

**Why.** A ready-labelled PR is, by definition, in the maintainers'
court awaiting review. Sweep 2's blanket "inactive open → draft" (and
Sweep 1's close / Sweep 3's draft) will otherwise yank a
maintainer-court PR out of the review queue purely for author
inactivity — the exact inverse of what the label means. Sweep 4
already re-classifies these by *whose court the ball is in* and hands
back only the author-court ones; Sweeps 1–3 must not pre-empt it. This
is the label-side analogue of the
[maintainer-court guard](#maintainer-court-guard-applies-to-every-sweep)
above.

---

## Sweep 1 — Stale drafts

Two sub-cases, both resulting in `close`:

### 1a. Triaged draft with no author reply ≥ 7 days

**Trigger.**

- `isDraft == true`
- **Not** carrying the `ready for maintainer review` label (per
  [Ready-label exclusion](#ready-label-exclusion-applies-to-sweeps-13) — Sweep 4's domain)
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
- **Not** carrying the `ready for maintainer review` label (per
  [Ready-label exclusion](#ready-label-exclusion-applies-to-sweeps-13) — Sweep 4's domain)
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
- **Not** carrying the `ready for maintainer review` label — the
  candidate search MUST include `-label:"ready for maintainer review"`
  (per [Ready-label exclusion](#ready-label-exclusion-applies-to-sweeps-13);
  these are Sweep 4's domain, never Sweep 2's)
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
- **Not** carrying the `ready for maintainer review` label (per
  [Ready-label exclusion](#ready-label-exclusion-applies-to-sweeps-13) — Sweep 4's domain)
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

`ready for maintainer review` means **the ball is in the maintainers'
court**. When a PR has carried the label for ≥ 7 days and gone quiet,
this sweep asks one question — *whose move is next?* — and acts on the
answer:

- **The next move is a maintainer's** (review, merge, workflow
  approval, CI rerun, branch update) → the label is **correct**. Leave
  it on; the PR is exactly where it belongs in the queue.
- **The next move is the author's** (resolve a conflict, fix a code /
  static failure, address an unresolved review thread, confirm
  readiness) → strip the label to hand the PR back, **and** post that
  author-facing action in the same pass.

The label is **never** stripped silently, and **never** stripped from a
PR a maintainer simply has not gotten to yet. Author silence alone is
not a strip trigger; only author silence *on a move that is the
author's to make* is. (This sweep used to strip every healthy stale PR
and close every rotted one — the inverse of the court rule: it
de-queued approved, mergeable PRs because their author had gone quiet,
and jumped straight to `close` on branches the author could still
rescue.)

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
[`<project-config>/pr-management-config.md → ready_for_maintainer_review_label`](../../projects/_template/pr-management-config.md)
— do not hard-code the string.

### Entry condition

A PR is a Sweep-4 candidate when **all** hold:

- it carries the `ready for maintainer review` label;
- the label was added ≥ 7 days ago (`<now> - ready_label_added_at >= 7
  days`, where `ready_label_added_at` is the most recent
  `LabeledEvent { label.name == <ready_label> }` timestamp from the
  PR's `timelineItems`);
- the PR has been quiet for ≥ 7 days — no commit, issue comment, or
  review by anyone since `<now> - 7 days`.

The label-age gate is the guard against the freshly-promoted misfire:
a PR promoted minutes ago has a recent label-add and is not a
candidate, so the queue is never yanked out from under a just-promoted
PR. The quiet-for-7-days gate keeps the sweep off PRs that are still
mid-conversation.

**Candidacy is not a verdict.** It means only "stale enough to
re-examine"; the disposition comes entirely from the court
re-classification in Steps A–B. Author silence is no longer a strip
trigger by itself — a silent PR whose next move is a maintainer's stays
labelled.

### Maintainer detection — committer, not `authorAssociation`

Every "maintainer" test in this sweep — and the
`last_maintainer_comment_at` / F5a / F5b signals it shares with
[`classify-and-act.md`](classify-and-act.md#maintainer-activity) —
means **a member of the `committers_team`** (see
[`<project-config>/pr-management-config.md`](../../projects/_template/pr-management-config.md))
**or** an account with repo permission `write`/`maintain`/`admin` —
**not** `authorAssociation ∈ {COLLABORATOR, MEMBER, OWNER}` alone.
GitHub returns `COLLABORATOR` for any triage/read collaborator, so
keying off it treats a read-only router's comment as maintainer
activity. Resolve it live for the small Sweep-4 candidate set when the
batch cannot prove committer status:

```bash
gh api repos/<upstream>/collaborators/<login>/permission --jq .permission   # want: write | maintain | admin
# or team membership:
gh api orgs/<org>/teams/<committers-team-slug>/memberships/<login> --jq .state  # want: active
```

A `read`/`triage` collaborator's comment does not establish
`last_maintainer_comment_at` and does not count as maintainer activity
here.

### Step A — re-classify live (whose move is next?)

Do **not** infer the disposition from label age or author silence —
re-classify the candidate against the live decision table. Branch state
is half of that, and the batched `mergeable` / `mergeStateStatus` is
unreliable here: GitHub computes mergeability lazily, so a batched
search over the `ready` queue returns `UNKNOWN` for many PRs and
`BLOCKED` for *most* (branch protection withholding the merge pending
the required approval they do not have yet). The Sweep-4 candidate set
is already small (stale ready PRs concentrate at the back of the
queue), so resolve mergeability **live, per candidate**:

```bash
gh api repos/<upstream>/pulls/<N> --jq '[.mergeable, .mergeable_state]|@tsv'
```

Classify the live `(mergeable, mergeable_state)` pair:

- `mergeable == true` and `mergeable_state ∈ {clean, has_hooks, unstable, behind, blocked}` → **healthy** (`blocked` is a clean branch withheld only on the missing approval — not bitrot).
- `mergeable == false` **or** `mergeable_state == dirty` → **conflicted** — author-court, only the author can rebase.
- `mergeable == null` / `mergeable_state == unknown` after the live call → **defer this run** (do not strip); it settles and re-qualifies next sweep.

`statusCheckRollup.state == FAILURE` is author-court when the failures
are the PR's own (a code / static fix is the author's move) and
maintainer-court when they are flaky / systemic (a rerun is ours) — the
decision table already draws that line (rows 10–13 `rerun` vs 12/12b/17
`comment`). This mirrors the live re-poll the
[`pr-management-quick-merge`](../pr-management-quick-merge/candidate-rules.md#stage-3--live-merge-readiness)
skill uses for the same reason — observed: a batch mergeability gate
misjudged ~87% of a real `ready` queue.

**Check the maintainer-court guard first.** If
[`author_question_to_maintainer_unanswered`](classify-and-act.md#author_question_to_maintainer_unanswered)
holds (pre-filter [F5c](classify-and-act.md#pre-filters) would
have skipped it in the interactive flow), the PR is maintainer-court
regardless of branch state — keep the label and stop. Resolve the
mentioned maintainer's committer status live (per the section above)
before relying on this, since it is the deciding signal.

Otherwise run the PR through the live decision table
([`classify-and-act.md`](classify-and-act.md)) to get its current
`(classification, action)`, resolving "maintainer" per the section
above. Step B reads the court off that result.

### Step B — court disposition

Read the court off the Step-A `(classification, action)`:

| Next move (decision-table action / state) | Court | Sweep-4 action |
|---|---|---|
| [`author_question_to_maintainer_unanswered`](classify-and-act.md#author_question_to_maintainer_unanswered) — author asked a maintainer, unanswered | maintainer (respond) | **keep label** — the author is waiting on us; never strip |
| `approve-workflow` | maintainer | **keep label**; perform the approval |
| `rerun` — flaky / systemic CI (rows 10/11/13) | maintainer | **keep label**; perform the rerun |
| `rebase` — branch behind, mergeable (row 16) | maintainer | **keep label**; perform the branch update |
| approved + mergeable (a committer approval present, CI green, not CONFLICTING) | maintainer (merge) | **keep label** — never strip |
| `mark-ready` / passing `skip` — green, never reviewed (rows 19/20) | maintainer (review) | **keep label** |
| `stale_review` — author already pushed after CHANGES_REQUESTED (row 18) | maintainer (re-review) | **keep label**; the row-18 `ping` is a reviewer nudge, not a strip |
| `mergeable == CONFLICTING` (row 9) | author (rebase) | **strip** + `ping` (rebase) + audit marker |
| author-caused CI / static failures (rows 12/12b/17) | author (fix) | **strip** + post the fix request + audit marker |
| `ping` — unresolved threads the author has not engaged (row 15) | author | **strip** + `ping` + audit marker |
| `request-author-confirmation` (row 14c) | author (confirm) | **strip** + post the request + audit marker |

A maintainer-court action that *does* something
(`approve-workflow` / `rerun` / `rebase`) is performed — the PR keeps
its label and progresses, joining that action's normal group. A
maintainer-court `mark-ready` / `skip` / re-review simply leaves the PR
labelled (no mutation): it is correctly in the queue.

### Strip and act in one pass

A strip and its author-facing action are a single unit of work **in
this pass** — never strip now and defer the ping to a later scan. The
author must never see the label vanish with no explanation and no
follow-up.

### Audit marker — every strip

[`strip-ready-label`](actions.md#strip-ready-label--remove-the-ready-for-review-label--audit-marker)
posts the
[`stale-ready-label-strip`](comment-templates.md#stale-ready-label-strip)
audit comment recording *what* was stripped, the *author-court reason*,
and the *next move*. When the author-facing action is itself a comment
(`ping` / `request-author-confirmation`), fold it into the **same**
comment rather than posting twice; a quality-flag `comment`/`draft`
keeps its own
[`triage_feedback_channel`](../../projects/_template/pr-management-config.md)
body and the audit marker accompanies it.

### Persistent bitrot — hand back, do not close

This sweep **hands rotted branches back** to the author (strip + ping);
it does **not** auto-close them. A PR that stays conflicted / red and
silent *after* the strip is retired by
[Sweep 2](#sweep-2--inactive-open-prs) (inactive open PR → draft after
4 weeks) like any other abandoned PR — there is no separate close timer
here. (The
[`stale-ready-label-close`](comment-templates.md#stale-ready-label-close)
template is retained only for a maintainer's explicit, manual close of
a long-dead ready PR.)

### Group behaviour

Author-court strips are a single `[A]ll`-confirmable group — reversible
and self-documenting (each carries its audit marker). The per-PR
**reason string must name the author-court trigger** ("merge conflict —
author must rebase", "unresolved threads, author not engaged", "failing
static checks — code fix needed", "awaiting author readiness
confirmation") — never a bare "ready label stale". PRs that
re-classify to a maintainer-court disposition are not in the strip
group at all.

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
[live mergeability re-poll](#step-a--re-classify-live-whose-move-is-next):
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
