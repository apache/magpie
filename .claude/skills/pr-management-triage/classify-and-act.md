<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Classify and act

Single-source decision file. Replaces the previous split between
`classify.md` and `suggested-actions.md`. Combines the two steps
that the old SKILL.md called Step 2 (classify) and Step 3
(suggest action) into one ordered decision table.

Reading order:

1. [Pre-filters](#pre-filters) — drop PRs that should never reach
   the maintainer this run.
2. [Decision table](#decision-table) — first-match-wins. Each row
   yields `(classification, action, reason)`.
3. [Precondition glossary](#precondition-glossary) — named
   compound predicates referenced from the table.
4. [Real-CI guard](#real-ci-guard) — mandatory check before any
   row that classifies a PR as `passing`.
5. [Grace periods](#grace-periods) — defers CI-failure flagging.
6. [Required GraphQL fields](#required-graphql-fields) — what the
   batch query must populate for this file to work.

Rationale, heuristic notes, override semantics, and the
draft-vs-comment-vs-ping discussion live in
[`rationale.md`](rationale.md). This file stays normative and
short; it is the only one the skill needs at decision time.

Classification + action selection is a **pure function of state**
populated by the single batched GraphQL query in
[`fetch-and-batch.md`](fetch-and-batch.md). No network calls, no
prompts, no writes.

---

## Pre-filters

Run these **before** the decision table. A PR that matches any
filter is skipped silently from the main triage flow.

| # | Filter | Match condition |
|---|---|---|
| F1 | Author is collaborator/member/owner | `authorAssociation ∈ {OWNER, MEMBER, COLLABORATOR}` (override: `authors:all` or `authors:collaborators`) |
| F2 | Author is a known bot | login is `dependabot`, `dependabot[bot]`, `renovate[bot]`, `github-actions`, `github-actions[bot]`, or matches `*[bot]`. Bot-authored **draft** PRs are handled separately by [`SKILL.md` Step 0.5](SKILL.md#step-05--promote-bot-authored-draft-prs) *before* this filter runs; F2 then drops the same logins from the main triage flow regardless of whether Step 0.5 promoted them. |
| F3 | Draft and not stale | `isDraft == true` and any activity within the last 14 days. Stale-sweep classifications in [`stale-sweeps.md`](stale-sweeps.md) may still pull the PR back in. |
| F4 | Already marked ready, no regression | `labels` contains `ready for maintainer review` AND CI green AND `mergeable != CONFLICTING` AND no unresolved **collaborator** threads (same collaborator-author qualifier as rows 19/20 / [`unresolved_threads_only`](#unresolved_threads_only) — contributor-author threads alone don't count as a regression for an already-ready PR). **Regression bypasses this filter** — any of: CI red, new conflict, or a new unresolved collaborator thread whose triggering event (failing check `startedAt`, conflict detection, thread `createdAt`) is *after* the label-add timestamp. The typical case is a contributor pushing a rebase or fixup commit to a ready-for-review PR that re-introduces deterministic failures, OR a maintainer leaving a new review thread post-label-add. PRs bypassing F4 fall through to the decision table normally; the cross-cutting [`strip-ready-on-downgrade` hard rule](#hard-rules-cross-cutting-the-table) ensures the label comes off if a `deterministic_flag` row fires. |
| F5a | Recent collaborator comment (author cooldown) | Most recent comment from the **union of** general-issue comments (`comments(last:10)`) and **review-thread comments** (`reviewThreads.nodes.comments`) is by a `COLLABORATOR`/`MEMBER`/`OWNER`, `createdAt < 72h` ago, AND posted after `commits(last:1).committedDate`. The review-thread leg is essential — a maintainer asking a clarifying question in-thread is just as much an active conversation as a top-level comment, and treating only the latter routes the PR to `ping` / `request-author-confirmation` while the maintainer is still mid-sentence. |
| F5b | Maintainer-to-maintainer ping unanswered | Most recent collaborator comment from the **union** described in F5a above `@`-mentions one or more logins other than the PR author AND none of those mentioned logins have posted on the PR (general comments **or** review threads) or in `latestReviews` after that comment. Team mentions (e.g. `@<upstream>-committers`) are conservatively treated as F5b matches. |
| F6 | Maintainer co-drafted | `isDraft == true` AND any of: (a) `latestReviews` has a node with `authorAssociation ∈ {OWNER, MEMBER, COLLABORATOR}` AND `author.login ≠ <viewer>` AND `state ∈ {COMMENTED, CHANGES_REQUESTED, APPROVED}` AND `submittedAt > commits(last:1).committedDate` AND review body is non-empty (avoids the "review with only inline thread comments and an empty top-level body" false positive — those are already counted by row 14/15 unresolved-thread logic); (b) `comments(last:10)` has a node with `authorAssociation ∈ {OWNER, MEMBER, COLLABORATOR}` AND `author.login ≠ <viewer>` AND `length(bodyText) ≥ 80` AND `createdAt > commits(last:1).committedDate`. Trivial signals (emoji-only, `+1`, `lgtm`, pure `@team` pings without prose) do not count — those are already covered by F5a/F5b or are below the substantive-engagement threshold. **Stale-sweep classifications in [`stale-sweeps.md`](stale-sweeps.md) may still pull the PR back in** — F6 only suppresses duplicate-proposal rows from the decision table, not eventual-resurfacing on a different action. |

F5a, F5b, and F6 override every signal in the decision table —
they are not weighed against conflicts, failing CI, or unresolved
threads. See
[`rationale.md#pre-filter-5-active-maintainer-conversation`](rationale.md#pre-filter-5-active-maintainer-conversation)
and
[`rationale.md#pre-filter-6-maintainer-co-drafted`](rationale.md#pre-filter-6-maintainer-co-drafted)
for the why.

---

## Decision table

PRs that survive the pre-filters are evaluated against the rows
below **top-to-bottom**. The first matching row wins; stop on
match. Each row produces a `(classification, action, reason)`
tuple consumed by [`interaction-loop.md`](interaction-loop.md).

Reasons in the table are templates; placeholder substitution is
described in [`#reason-template-rules`](#reason-template-rules).
Action verbs are defined in [`actions.md`](actions.md).

| #  | Precondition (all must hold)                                                                  | Classification             | Action                  | Reason template |
|----|-----------------------------------------------------------------------------------------------|---------------------------|------------------------|-----------------|
| 1  | `head_sha` appears in the per-page `action_required` REST index, OR ([`first_time_no_real_ci`](#first_time_no_real_ci))     | `pending_workflow_approval` | `approve-workflow`     | First-time contributor — review the diff and approve CI, or flag suspicious |
| 2  | [`copilot_review_stale`](#copilot_review_stale)                                               | `stale_copilot_review`     | `draft` (include the specific Copilot thread URL in the violation body) | Unaddressed Copilot review ≥ 7 days old — convert to draft |
| 3  | Viewer comment containing the triage marker exists, posted after last commit, age < 7 days, sub-state `waiting` | `already_triaged`         | `skip`                 | Already triaged M days ago — still waiting on author |
| 4  | Same as #3 but sub-state `responded`                                                           | `already_triaged`          | `skip`                 | Already triaged M days ago — author responded, maintainer to re-engage |
| 5  | Viewer triage marker exists, posted after last commit, sub-state `waiting`, age ≥ 7 days, `isDraft == true` | `stale_draft`     | (defer to [`stale-sweeps.md`](stale-sweeps.md) Sweep 1a) | Draft triaged N days ago, no author reply |
| 6  | `viewer == pr.author.login`                                                                   | n/a                        | `skip`                 | You are the PR author — triage skipped |
| 7a | `now - createdAt < 30min`                                                                      | n/a                        | `skip`                 | Too fresh — CI still warming up |
| 7b | [`security_language_signal`](#security_language_signal)                                        | `security_language_signal` | `comment`              | Security-language in title / body / commits — ask contributor to neutralise or confirm CVE disclosure complete |
| 8  | `flagged_prs_by_author > 3` AND [`has_deterministic_signal`](#has_deterministic_signal)        | `deterministic_flag`       | `close`                | Author has N flagged PRs — suggest closing to reduce queue pressure |
| 9  | `mergeable == CONFLICTING`                                                                    | `deterministic_flag`       | `draft`                | Merge conflicts with `<base>` — author must rebase locally; convert to draft with merge-conflicts violation |
| 10 | [`ci_failures_only`](#ci_failures_only) AND every failure ∈ `recent_main_failures`             | `deterministic_flag`       | `rerun`                | All N CI failures also appear in recent main-branch PRs — likely systemic, suggest rerun |
| 11 | [`ci_failures_only`](#ci_failures_only) AND any failure ∈ `recent_main_failures`               | `deterministic_flag`       | `rerun`                | K/N CI failures match recent main-branch PRs — likely systemic |
| 12 | [`ci_failures_only`](#ci_failures_only) AND every failed check is a [static check](#static_check) | `deterministic_flag`     | `comment`              | Only static-check failures — needs a code fix, not a rerun |
| 13 | [`ci_failures_only`](#ci_failures_only) AND `failed_count <= 2` AND `commits_behind <= 50`     | `deterministic_flag`       | `rerun`                | N CI failure(s) on otherwise clean PR — likely flaky, suggest rerun |
| 14a | [`author_confirmation_received`](#author_confirmation_received)                                | `author_confirmed_ready`   | `mark-ready`           | Author confirmed PR is ready for maintainer review — apply label |
| 14b | [`pending_author_confirmation`](#pending_author_confirmation)                                  | `awaiting_author_confirmation` | `skip`             | Awaiting author confirmation requested M days ago |
| 14c | [`unresolved_threads_only`](#unresolved_threads_only) AND [`unresolved_threads_only_likely_addressed`](#unresolved_threads_only_likely_addressed) | `deterministic_flag` | `request-author-confirmation` | K unresolved thread(s) from <reviewers> show author engagement — ask author to confirm readiness for maintainer review |
| 15 | [`unresolved_threads_only`](#unresolved_threads_only)                                          | `deterministic_flag`       | `ping`                 | K unresolved review thread(s) from <reviewers> — ping author + reviewers |
| 16 | No real CI ran (see [Real-CI guard](#real-ci-guard)) AND `mergeable != CONFLICTING` AND author NOT first-time | `deterministic_flag` | `rebase`            | No real CI checks triggered, branch mergeable — rebase to re-trigger |
| 17 | [`has_deterministic_signal`](#has_deterministic_signal) (fallback)                             | `deterministic_flag`       | `draft`                | Has quality issues — convert to draft with violations comment |
| 18 | `latestReviews` has CHANGES_REQUESTED AND author committed after AND NOT [`follow_up_ping`](#follow_up_ping) | `stale_review`         | `ping`                 | Author pushed commits after CHANGES_REQUESTED from <reviewers> but no follow-up — ping |
| 19 | All of: `statusCheckRollup.state == SUCCESS`, `mergeable != CONFLICTING`, no unresolved **collaborator** threads (see [`unresolved_threads_only`](#unresolved_threads_only) for the collaborator-author qualifier), [Real-CI guard](#real-ci-guard) passes, label `ready for maintainer review` already present | `passing` | `skip` | Already marked ready for review |
| 20 | All of: `statusCheckRollup.state == SUCCESS`, `mergeable != CONFLICTING`, no unresolved **collaborator** threads (see [`unresolved_threads_only`](#unresolved_threads_only) for the collaborator-author qualifier), [Real-CI guard](#real-ci-guard) passes | `passing` | `mark-ready` | All checks green, no conflicts, no unresolved collaborator threads — mark for deeper review |
| 21 | Stale-sweep candidate (see [`stale-sweeps.md`](stale-sweeps.md)) AND no row 1–20 matched in this session | `stale_draft` / `inactive_open` / `stale_workflow_approval` | (per sweep) | (per sweep) |
| 22 | Data inconsistency: rollup `SUCCESS` with `failed_checks` non-empty, OR rollup `FAILURE` with `failed_checks` empty (e.g. only CANCELLED contexts visible, or rollup hasn't yet propagated the failing check-run). Evaluated **before** rows 17, 19-20 — see [hard rules](#hard-rules-cross-cutting-the-table) | n/a | `skip` | Data anomaly — rollup not yet settled, retry next page |

### Hard rules cross-cutting the table

- **Never suggest `rebase` on a CONFLICTING PR.** GitHub's
  update-branch endpoint does a side-merge and refuses on
  conflicts. Row 9 catches this before any rebase row can fire.
  Action-side guard: see the `rebase` recipe in [`actions.md`](actions.md).
- **Never `mark-ready` while workflow approval is pending.**
  Row 1 catches the upstream signal; the
  [`mark-ready` action](actions.md#mark-ready--add-ready-for-maintainer-review-label) re-checks the
  REST `action_required` index immediately before mutating
  (Golden rule 1b in [`SKILL.md`](SKILL.md)).
- **Collaborator-authored PRs never get `draft`.** When
  `authors:collaborators` is active, fall back to `comment` with
  the same body. Row 9 / 17 / etc. emit `comment`, not `draft`,
  in that mode.
- **Row 22 fires before rows 17, 19-20.** A PR matching the
  row 22 precondition (rollup SUCCESS but `failed_checks`
  non-empty; rollup FAILURE but `failed_checks` empty; or other
  rollup-vs-context inconsistency) must reach neither the row
  17 `deterministic_flag` fallback nor the `passing` rows.
  Implementations evaluate row 22's precondition immediately
  before evaluating row 17; the row's table position (last) is
  documentary, not evaluation order. The rollup-FAILURE-with-
  empty-`failed_checks` direction is naturally enforced by
  [`has_deterministic_signal`](#has_deterministic_signal)'s
  non-empty-`failed_checks` clause — that case fails every
  decision row, falls through to row 22, and skips. The
  rollup-SUCCESS-with-non-empty-`failed_checks` direction needs
  the explicit pre-row-19 check, since the `passing` rows only
  inspect `rollup.state`.
- **`strip-ready-on-downgrade`: strip `ready for maintainer
  review` when a regressed PR matches a `deterministic_flag`
  row.** When a PR carrying the `ready for maintainer review`
  label bypasses [F4](#pre-filters) (rebased / pushed with new
  deterministic failures) and matches any `deterministic_flag`
  row whose action is `draft`, `comment`, or `close`, the
  action MUST also remove the label. The label's contract is
  "no maintainer time wasted on quality issues" — leaving it on
  a PR we are now flagging *is* the false-positive the label is
  meant to prevent, and it lets a regressed PR keep priority in
  the review queue. Actions `rerun`, `rebase`, and `ping` do
  NOT strip the label: those classify the regression as
  transient (flaky CI, missing base merge, reviewer hasn't
  responded) and the label is still informative if the
  follow-up succeeds.

  **Exception — merit-discussion-in-flight.** If
  [`merit_discussion_thread_present`](#merit_discussion_thread_present)
  holds on the regressed PR, the strip-ready-on-downgrade
  rule does **not** fire. Additionally:

    - A `draft` action skips the `gh pr ready --undo` step
      (the PR stays out of draft). The violations comment is
      still posted so mechanical issues remain surfaced for
      the author. The action effectively degrades to a
      `comment` action that preserves the label.
    - A `close` action skips the close step (the PR stays
      open). The comment is still posted; the
      quality-violations label is still applied. Closing a PR
      with an active maintainer review discussion is more
      destructive than the queue-pressure problem `close`
      exists to solve.
    - A `comment` action posts the violations comment but
      does not strip the label.

  Rationale: the `ready for maintainer review` label exists
  to attract senior eyes, and an unresolved maintainer review
  thread is exactly the moment those eyes are most valuable.
  Stripping the label or pushing the PR back to draft
  mid-discussion makes it disappear from the maintainer queue
  at the worst possible time. CI red / lint failures / merge
  conflicts and a live design debate are orthogonal: a
  maintainer can weigh in on design even when CI is red. The
  precondition is deliberately broad — contributor-author
  threads alone do not satisfy it (those are not the merit
  signal the label defers to), but any maintainer-opened
  unresolved thread does, regardless of body length or when
  it was opened relative to the label-add. Source: user-scope
  feedback memory
  `feedback-ready-for-maintainer-review-label`.

  Implementation: see
  [`actions.md#draft`](actions.md#draft--convert-to-draft-and-post-violations-comment),
  [`actions.md#comment`](actions.md#comment--post-violations--stale-review--ping-comment),
  and [`actions.md#close`](actions.md#close--close-with-comment-and-quality-violations-label).

---

## Precondition glossary

Compound predicates referenced from the decision table. Defined
once here so the table rows stay short and unambiguous.

### `has_deterministic_signal`

At least one of:

- `mergeable == CONFLICTING`
- `statusCheckRollup.state == FAILURE` AND
  [`failed_checks`](#failed_checks) is non-empty AND PR is past
  its [grace window](#grace-periods). The non-empty
  `failed_checks` clause routes rollup-FAILURE-without-
  extractable-failed-checks (the rollup has rolled to FAILURE
  but no contributing context is visible — typically because
  the only completed contexts are CANCELLED, or the rollup
  hasn't yet propagated the check-run that flipped it) to
  [row 22](#decision-table) instead of cascading down to the
  row 17 draft fallback with an empty violation list.
- `reviewThreads.totalCount` ≥ 1 with `isResolved == false` AND
  the thread's reviewer is `COLLABORATOR`/`MEMBER`/`OWNER`

### `security_language_signal`

The PR title, body, or any commit message matches at least one of
the following patterns (case-insensitive). Evaluated against:
`title`, `body`, and all items in `commits.nodes[].message` from
the GraphQL response (up to the last 250 commits).

- **CVE IDs**: `CVE-\d{4}-\d+`
- **Phrases**: "security vulnerability", "security issue",
  "security fix", "security bug", "security flaw",
  "security patch", "arbitrary code execution",
  "remote code execution", `RCE`, "SQL injection", `XSS`,
  `CSRF`, `SSRF`, "path traversal", "directory traversal",
  "privilege escalation", "auth bypass", "authentication bypass",
  "authorization bypass", "insecure deserialization",
  "heap overflow", "buffer overflow", "use-after-free",
  "exploit", "exploitable"

When building the comment, record every match with its location
(title / body / commit SHA + first 72 chars of message) so the
`<security_matches>` placeholder in
[`comment-templates.md#security-language-comment`](comment-templates.md#security-language-comment)
can be populated verbatim.

---

### `ci_failures_only`

`has_deterministic_signal` is true AND the *only* signal that
fired is the CI-failure one (no `CONFLICTING`, no unresolved
collaborator threads).

### `failed_checks`

The list of `statusCheckRollup.contexts` entries whose terminal
state indicates a real failure attributable to the PR's code:

- `CheckRun.conclusion ∈ {FAILURE, TIMED_OUT}`, OR
- `StatusContext.state ∈ {FAILURE, ERROR}`.

Excluded:

- **`CheckRun.conclusion == CANCELLED`.** Cancellation is
  almost always caused by a newer push superseding an in-flight
  run, GitHub Actions concurrency-cancellation, or the
  contributor cancelling manually — none of these signal that
  the PR's current head SHA is broken. Cancelled contexts may
  still pull `statusCheckRollup.state` to `FAILURE`, which is
  why `has_deterministic_signal` requires `failed_checks`
  non-empty rather than trusting the rollup state alone.
- `CheckRun.conclusion ∈ {NEUTRAL, SKIPPED, STALE,
  STARTUP_FAILURE, ACTION_REQUIRED}` — non-failure conclusions
  or infra issues. `ACTION_REQUIRED` in particular is the
  workflow-approval-pending signal handled by row 1, not a
  per-check failure.
- Pending checks (`status ∈ {QUEUED, IN_PROGRESS, PENDING}`
  or `conclusion == null`) — counted separately as
  `pending_checks` and not eligible for any deterministic-flag
  row.

Implementations may track `cancelled_checks` and
`pending_checks` separately for diagnostics / reason templates,
but only `failed_checks` feeds the decision table.

### `unresolved_threads_only`

`has_deterministic_signal` is true AND the *only* signal that
fired is unresolved threads (`statusCheckRollup.state` is
`SUCCESS`, `mergeable != CONFLICTING`).

### `merit_discussion_thread_present`

True when the PR has at least one unresolved review thread
whose first comment is from a `COLLABORATOR`/`MEMBER`/`OWNER`
(the same collaborator-author qualifier as
[`unresolved_threads_only`](#unresolved_threads_only)).

This is the "active maintainer review discussion" signal. No
timing qualifier is applied — a substantive design / approach
/ scope / correctness discussion can have started either
before or after the `ready for maintainer review` label was
added, and in either case the label must not be stripped
while the discussion is in flight. The precondition
deliberately does not filter by body length or thread
content: an explicit maintainer act of opening a review
thread is treated as substantive engagement on its own.
Contributor-author unresolved threads do NOT satisfy this
precondition (mirrors the
[`unresolved_threads_only`](#unresolved_threads_only)
collaborator qualifier — contributor-to-contributor side
chatter is not a merit discussion the label should defer to).

Source: user-scope feedback memory
`feedback-ready-for-maintainer-review-label`. See the
[`strip-ready-on-downgrade`](#hard-rules-cross-cutting-the-table)
hard rule for how this precondition gates the label-strip,
draft-conversion, and close behavior on a regressed PR.

### `unresolved_threads_only_likely_addressed`

All of:

- The PR's latest `committedDate` is **after** the most recent
  unresolved-thread first-comment `createdAt`.
- For every unresolved thread, either the author has replied
  in-thread (`comments.nodes.author.login == pr.author.login`
  AND `createdAt >` first-comment `createdAt`) OR a commit was
  pushed after the thread's first-comment `createdAt`.

Heuristic, conservative on purpose. Rationale:
[`rationale.md#unresolved_threads_only_likely_addressed-heuristic-detail`](rationale.md#unresolved_threads_only_likely_addressed-heuristic-detail).

### `viewer_confirmation_request_present`

True when the viewer (the authenticated maintainer running the
skill) has posted a comment on the PR whose body contains the
literal marker string

> `ready for maintainer review confirmation`

(the canonical marker baked into the `request-author-confirmation`
template — see
[`comment-templates.md#request-author-confirmation`](comment-templates.md))
AND that comment's `createdAt` is **after** the PR's head
`committedDate`. The post-last-commit check means a fresh
contributor push invalidates the prior confirmation request
(new code = new threads possibly opened, our previous question
no longer applies).

Marker matching is a case-sensitive substring search on the
comment body. The marker text is fixed in the framework template
to make this glossary entry deterministic; adopters customising
the wording of the rest of the body must keep this exact string
verbatim — the same contract as the
[`Pull Request quality criteria`](#decision-table) link text
for `already_triaged` (rows 3–4).

### `pending_author_confirmation`

[`viewer_confirmation_request_present`](#viewer_confirmation_request_present)
is true AND there is **no** comment by the PR author (issue-level
in `comments(last:10)` **or** review-thread reply in
`reviewThreads.nodes.comments`) with `createdAt` greater than
the confirmation-request comment's `createdAt`.

The PR is mid-cycle: we have asked, the author has not yet
answered.

### `author_confirmation_received`

[`viewer_confirmation_request_present`](#viewer_confirmation_request_present)
is true AND there **is** a comment by the PR author (issue-level
or review-thread reply, as in
[`pending_author_confirmation`](#pending_author_confirmation))
with `createdAt` greater than the confirmation-request comment's
`createdAt`.

The author has responded. The reply text is **not** parsed by
the bot — the triaging maintainer reads the reply alongside the
proposal in
[`interaction-loop.md`](interaction-loop.md) and decides
whether the response is affirmative. If the maintainer reads
the reply as a non-affirmative response ("still working on X",
a follow-up question, etc.) they override the proposal to
`skip` or `[O]ping`. The bot's only job is to surface the PR
with the reply visible.

### `copilot_review_stale`

The PR has at least one unresolved review thread whose first
comment author matches a Copilot bot login (case-insensitive:
`copilot-pull-request-reviewer[bot]`, `copilot[bot]`,
`github-copilot[bot]`, or any login matching `copilot*[bot]` /
`github-copilot*[bot]`) AND that comment's `createdAt` is ≥ 7
days ago AND no author reply in the same thread or on the PR
after that timestamp.

### `static_check`

Failed check name (case-insensitive substring match either
direction) hits one of: `static check`, `pre-commit`, `lint`,
`mypy`, `ruff`, `black`, `flake8`, `pylint`, `isort`, `bandit`,
`codespell`, `yamllint`, `shellcheck`, `spellcheck`,
`spelling`, `build documentation`, `build docs`, `build-docs`.
Additional patterns may be configured in
`<project-config>/pr-management-triage-ci-check-map.md`.

The doc-build / spellcheck patterns are included in the
framework defaults because the failure mode is symmetric with
the other static checks: the contributor introduced text the
checker doesn't accept (a misspelled word, a broken docs
include, a missing sphinx reference) and the fix is a code
change, not a CI rerun. Without these patterns row 13 (`rerun`)
fires on a single docs failure and the bot sends a useless
rerun request that fails identically.

### `recent_main_failures`

Cached set of failing check names from the most recent 10
merged PRs on `<base>`. Built by the recent-main-branch-failures
query in [`fetch-and-batch.md`](fetch-and-batch.md).
Cache TTL 4 hours. A check name appearing in ≥ 2 of the 10
sampled PRs is "systemic".

### `flagged_prs_by_author`

Count of PRs by the same author seen on the **current page** that
already matched a `deterministic_flag` row. Per-page only — does
not persist across sessions.

### `first_time_no_real_ci`

Author is `FIRST_TIME_CONTRIBUTOR` or `FIRST_TIMER` AND one of:

- `statusCheckRollup.state` is `EXPECTED` or empty (no contexts), OR
- `statusCheckRollup.state` is `SUCCESS` but no
  `statusCheckRollup.contexts` matches a real-CI pattern (see
  [Real-CI guard](#real-ci-guard)).

Catches the case where the per-page `action_required` REST index
is empty / stale or the run is not yet indexed, but the rollup
shape still indicates real CI has not executed.

### `follow_up_ping`

True when at least one of the following resolves the apparent
`stale_review` (Row 18):

- A comment by the PR author after the most recent
  `CHANGES_REQUESTED` review (`comments(last:10)` or
  `reviewThreads.nodes.comments`) whose body `@`-mentions the
  reviewer login.
- A comment by the reviewer (general or review-thread) after
  the author's most recent commit
  (`commits(last:1).committedDate`).
- The PR author's most recent commit is **less than 24 hours
  old**. The push itself is the follow-up — they're still
  actively working through the reviewer's feedback. Pinging
  immediately reads as the bot rushing them. (24 h is the
  shortest gap that lets the author finish a fixup-and-push
  cycle without an interruption; the broader F5a 72h cooldown
  applies on the maintainer side.)

Any of these signals indicates the conversation is alive and a
fresh ping would talk over an existing exchange. False
otherwise.

---

## Real-CI guard

**Mandatory before any row that classifies a PR as `passing`
(rows 19, 20).** Also fires before row 16's "no real CI ran"
detection.

A PR can have `statusCheckRollup.state == SUCCESS` while every
real CI run is held in `action_required`. The rollup aggregates
only completed check-runs; fast bot checks (`Mergeable`, `WIP`,
`DCO`, `boring-cyborg`) succeed unconditionally and pull the
rollup to SUCCESS before real CI is allowed to start.

Walk `statusCheckRollup.contexts.nodes` and confirm at least one
context's name matches a real-CI pattern. If none match,
reclassify:

- If the per-page `action_required` REST index has any runs at
  the PR's head SHA, route to row 1 (`pending_workflow_approval`).
  Catches the case where the GraphQL rollup has not yet
  reflected a workflow run that was approved between fetch
  time and the guard run.
- Otherwise, route to row 16 (`rebase`).

Note: the `FIRST_TIME_CONTRIBUTOR` / `FIRST_TIMER` case is
already handled by row 1's `first_time_no_real_ci` precondition,
so it never reaches the guard. The row 1 / guard split is
belt-and-braces — any first-time PR with no real CI is caught
upstream.

Real-CI patterns are read from `<project-config>/pr-management-config.md`
at session start (field `real_ci_patterns`, list of regex strings).
The list below shows the **shape** of what a typical project might
configure; concrete values live in the adopter config:

- `Tests` (exact or as prefix)
- `Tests \(.*\)` (matrix splits)
- `Static checks` / `Pre-commit`
- `Lint` / `Type check`
- `Build` / `Image`
- `Docs`
- `Security scan` (e.g. `CodeQL`, `bandit`, `trivy`)
- Project-specific checks (e.g. `newsfragment`, `changelog`, `license`)

Bot/labeler noise (`Mergeable`, `WIP`, `DCO`, `boring-cyborg`,
`probot`, etc.) does NOT count.

---

## Grace periods

Apply only to the CI-failure leg of `has_deterministic_signal`.
Conflicts and unresolved threads do not have a CI-style grace
window — they are gated by pre-filter F5a (the 72-hour
author-response cooldown) instead.

| Condition on the PR | Grace window |
|---|---|
| No collaborator engagement (no review, no comment from a `COLLABORATOR`/`MEMBER`/`OWNER`) | **24 hours** |
| At least one collaborator has commented or reviewed | **96 hours** |

Computed from the most recent failing check's `startedAt` (fall
back to `completedAt`, then to PR `updatedAt`). If still inside
the grace window, treat the CI-failure signal as not-fired for
purposes of the decision table — the PR may still classify on a
conflict or unresolved-thread signal, or fall through to row 20
if it has none.

Record the effective grace result on the PR record so reason
templates can include "CI failed Xh ago, Yh remaining" if
desired.

---

## Reason template rules

Reason strings are rendered verbatim to the maintainer in the
proposal and (for actions that post a comment) included in the
body. Rules:

- One line. Factual. Lead with the signal that fired the rule;
  end with the proposal verb where applicable.
- Substitute placeholders (`<base>`, `<reviewers>`, `N`, `K`,
  `M`) from the PR record. `<reviewers>` is `@login` mentions
  joined with a comma followed by a single space — see the canonical example
  below. Substitution happens at classification time;
  [`interaction-loop.md`](interaction-loop.md) displays the
  already-substituted string verbatim.
- Never editorialise. Never include emoji or scare quotes.
- Never include LLM-generated prose; the templates above are the
  full surface area.

Examples:

> Only static-check failures (ruff, mypy-core) — suggest comment
>
> 3/5 CI failures also appear in recent main-branch PRs — likely systemic, suggest rerun
>
> Merge conflicts with `main` + 73 commits behind — suggest draft
>
> 2 unresolved review threads from @potiuk, @uranusjr — suggest ping

Avoid:

> This PR has issues — suggest draft
>
> Not good enough — close it
>
> 🚨 Failing CI 🚨

---

## Required GraphQL fields

Adding a new row to the decision table? Cross-check this list
first; if a field isn't already populated, extend the batch query
in [`fetch-and-batch.md`](fetch-and-batch.md) before writing the
classification logic. Golden rule "one query per page" still
applies — rows do not get to reach back for more data.

| Decision rows / preconditions | Required fields |
|---|---|
| F5a, F5b, F6, grace periods | `comments(last:10).nodes.{author.login,authorAssociation,bodyText,createdAt}`, `reviewThreads.nodes.comments(first:5).nodes.{author.login,authorAssociation,bodyText,createdAt}`, `latestReviews.nodes.{state,author.login,authorAssociation,submittedAt}`, `commits(last:1).nodes.commit.committedDate`, viewer login |
| Row 1 + Real-CI guard | `statusCheckRollup.state`, `statusCheckRollup.contexts`, `authorAssociation`, `head_sha` (REST `action_required` index keyed by `head_sha`) |
| `copilot_review_stale` (row 2) | `reviewThreads.nodes.{isResolved,comments.nodes.{author.login,createdAt,url}}`, `comments(last:10).nodes.{author.login,createdAt}` |
| `has_deterministic_signal`, `ci_failures_only`, `unresolved_threads_only`, `unresolved_threads_only_likely_addressed` (rows 8–17) | `mergeable`, `statusCheckRollup.{state,contexts}`, `reviewThreads.nodes.{isResolved,comments(first:5).nodes.{author.login,authorAssociation,createdAt}}`, `updatedAt`, `comments(last:10).nodes.{author.login,authorAssociation,createdAt}`, `commits(last:1).nodes.commit.committedDate`, `author.login` |
| Row 18 (`stale_review`) | `latestReviews.nodes.{state,author.login,submittedAt}`, `commits(last:1).nodes.commit.committedDate`, `comments(last:10)`, `reviewThreads.nodes.comments(first:5).nodes.{author.login,createdAt}` |
| Rows 3–5 (`already_triaged` / `stale_draft` from triage marker) | `comments(last:10).nodes.{author.login,bodyText,createdAt}`, viewer login, `commits(last:1).nodes.commit.committedDate` |
| Rows 19, 20 (`passing`) | `statusCheckRollup.state`, `statusCheckRollup.contexts`, `mergeable`, `reviewThreads.totalCount`, `labels` |

---

## Where the prose went

- Why each rule exists, the heuristic discussion behind
  `unresolved_threads_only_likely_addressed`, the draft-vs-comment-vs-ping
  reasoning, override semantics, and the
  refuse-to-suggest cases all moved to
  [`rationale.md`](rationale.md). Numbering matches the decision
  table rows so a maintainer can jump from a row to its
  rationale in one click.
- Pre-filter rationale (especially the "rush the contributor /
  talk over a maintainer" framing) is in
  [`rationale.md#pre-filter-5-active-maintainer-conversation`](rationale.md#pre-filter-5-active-maintainer-conversation).
