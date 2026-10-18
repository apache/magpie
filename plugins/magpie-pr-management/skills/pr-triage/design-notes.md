<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Design notes

Why the cross-cutting rules of `pr-management-triage` are the way they are.
Not in the skill's hot path: read it when a maintainer asks why a PR was handled that way, when a rule's effect is contested, or before changing a rule in [`tools/pr-management`](../../../../tools/pr-management/README.md).
The *why* of each individual row lives with that row, under [`classifications/`](classifications/).

---

## Pre-filter 5 (active maintainer conversation)

F5a (author-response cooldown), F5b (maintainer-to-maintainer
ping), and F5c (author question to a maintainer) override every
signal in the decision table. Three cases, same underlying
principle: do not let the triage skill talk over — or pre-empt —
a human conversation that needs a human's next move.

### F5a — 72-hour cooldown after collaborator feedback

When a maintainer just engaged with the PR, the author deserves
at least three days to read, think, and reply before the triage
skill auto-drafts or auto-comments on top of that conversation.

Why 72 hours and not 24:

- Review-style feedback takes longer to address than a flaky-CI
  nudge.
- A same-day auto-action reads as the bot talking over the
  maintainer.
- The 24-hour window in [grace
  periods](../../../../tools/pr-management/README.md#shared-rules) is for *CI*
  failures the author may not have noticed yet — different
  failure mode, different patience budget.

Cost asymmetry: a missed auto-action on one of these PRs is one
extra day of queue presence. An auto-action that talks over a
maintainer is a contributor reading the project as chaotic. Prefer
the former.

A maintainer may leave feedback in a general comment, an inline
comment, or a submitted review body with no inline thread. All three
need the same cooldown; omitting the last source caused
[#78](https://github.com/apache/magpie/issues/78). The latest feedback
across those sources decides, so a later author response releases
the cooldown. The exact source, body and timestamp conditions are in
[the decision table](../../../../tools/pr-management/README.md#shared-rules), F5a.

### F5b — maintainer-to-maintainer ping unanswered

When a maintainer pings other maintainers (e.g.
*"@ash @kaxil could you weigh in on the API shape?"*), the PR is
waiting on **maintainer input**, not on author work.
Auto-drafting it with a "the author should work on comments"
message is wrong on two counts:

- The contributor isn't the bottleneck — the maintainer review
  / conversation is.
- It de-focuses the thread away from the maintainer-to-
  maintainer discussion the original commenter was trying to
  start.

Skip silently until one of the pinged collaborators responds, at
which point F5a's 72-hour window starts ticking from that reply.

Team mentions (`@<upstream>-committers`) are conservatively
treated as F5b matches — we cannot cheaply expand team membership
in the batch query, and the false-positive cost (skipping a PR
that should have been actioned) is much lower than the false-
negative cost (talking over a real maintainer call-out).

### F5c — author question to a maintainer unanswered

The mirror image of F5b. F5b is *maintainer → maintainer*; F5c is
*author → maintainer*. When the author's most recent comment pings
a maintainer (*"@potiuk I rebased and answered your point — could
you take another look?"*, or any open question directed at the
team) and no maintainer has replied since, the PR is waiting on
**us**, not on the author. The ball is in the maintainers' court.

Without F5c the classifier reads "last comment by author, then
silence" the same way it reads an abandoned PR, and routes it to an
author-facing action — ping the author, request readiness
confirmation, convert to draft, or (via the stale sweeps) close it
for inactivity. Every one of those is wrong here: the contributor
already did their part and asked us a question; handing the PR back
to them, or closing it, tells a contributor who was waiting politely
that the project dropped their question on the floor. That is the
single most corrosive contributor experience the skill can produce —
and it is exactly what happened to a real PR that the triage process
closed while an open question to the team sat unanswered, later
reopened by hand with an apology.

The override is deliberately as strong as F5a/F5b — it beats a merge
conflict and red CI. If the author asked a question *and* CI is red,
auto-pinging "please fix CI" while ignoring their question is the
talk-over we are trying to prevent. The maintainer answers, and if a
CI fix is also needed they say so themselves, in their own voice.

Maintainer status is resolved the same load-bearing way as F5b and
Sweep 4 — a `COLLABORATOR` mention is confirmed against the
committers team / repo-permission API before it is trusted, so a
ping at a read-only collaborator does not falsely park the PR in our
court. Team mentions are conservatively treated as matches, same as
F5b. The detection is `@`-mention-based on purpose: "did the author
ask a question?" is not cheaply decidable, but "did the author ping
a maintainer with no reply since?" is, and it is the deterministic
core of the case. A maintainer reading the surfaced PR makes the
final call on whether an answer is owed.

---

## Pre-filter 6 (maintainer co-drafted)

F6 covers a different shape of "do not talk over a maintainer"
than F5a/F5b: a draft PR that a maintainer (other than the
viewer running the skill) has already substantively engaged
with — typically by leaving a review with `CHANGES_REQUESTED`,
posting a substantive comment outlining what is wrong, or both —
and where the author has not yet responded with a new commit.

The motivating cases are PRs the maintainer would already
demote-and-comment on by hand and which the classifier, running
later, would propose the same `draft` action for a second time.
A few historical examples on `<upstream>` (each manually skipped
to avoid a duplicate proposal):

- `potiuk-drafted` `<upstream>#58149`
- `vargacypher-drafted` `<upstream>#63260`
- `bugraoz93-drafted` `<upstream>#64906`

In each case the classifier wanted to emit a `deterministic_flag
→ draft` proposal whose substance a different maintainer had
already covered on the draft. F5a does not cover this: F5a
expires after 72 hours and only fires when the **most recent**
feedback (comment, review-thread comment, or submitted review) is
by a collaborator. F5b does not cover this either:
the maintainer engagement here is directed at the author, not at
other maintainers. F6 closes the gap.

### Empirical check against the motivating examples

Snapshotting the three PRs at the time of the issue (`<now>` =
2026-05-07):

| PR | Last author commit | Qualifying maintainer engagement after that anchor | F6 fires (viewer = potiuk)? |
|---|---|---|---|
| `<upstream>#63260` | 2026-03-22 (vargacypher) | `kaxil` comment 2026-04-15, body length 80 chars | yes — comment branch |
| `<upstream>#64906` | 2026-04-11 (stephen-bracken) | `bugraoz93` comment 2026-04-20, body length 102 chars | yes — comment branch |
| `<upstream>#58149` | 2026-01-23 (Philip Abernethy) | only `potiuk`'s own triage / closure comments | **no** — viewer-self engagement is excluded |

`#58149` is therefore not addressed by F6 as written. It is a
related-but-distinct concern: the viewer's *own* prior
engagement on a draft is conceptually
[`already_triaged`](classifications/already-triaged.md)
territory (rows 3–5), and the duplicate-proposal symptom there
is "viewer left a free-form drafting comment that doesn't carry
the triage marker, so rows 3–5 don't recognise it." Closing
that gap belongs in the marker-detection logic of rows 3–5 (or
in the stale-sweep duplicate-suppression), not in F6 — F6's
contract is "do not talk over a *different* maintainer." The
issue tracking the marker-detection extension is
[#79's first follow-up bullet](https://github.com/apache/magpie/issues/79).

### Why drafts only, not ready-for-review

The F6 signal is "a maintainer is co-drafting this PR" — a
collaborative state that only exists while the PR is `isDraft ==
true`. Once a PR is promoted to ready-for-review the surrounding
semantics flip: F4 already exempts ready PRs without regression,
and a regression on a ready PR is exactly the moment we *want*
the classifier to surface a signal to the maintainer queue, not
suppress it. Limiting F6 to drafts keeps that signal path
intact.

### Why "after the last author commit", not a wall-clock TTL

A wall-clock expiry (e.g. "ignore engagements older than 30
days") would re-introduce the same duplicate-proposal problem
F6 is meant to avoid: an old draft that a maintainer engaged
with months ago, which the author has not pushed to since, is
still in the same conversational state — re-proposing `draft`
on it adds nothing. The right invalidation signal is **author
activity**, not time: when the author pushes a new commit, the
maintainer's prior critique may or may not be addressed and the
classifier should re-evaluate. Anchoring F6 at
`commits(last:1).committedDate` matches F5a's anchor and lets
the eventual-resurfacing job stay where it belongs — the stale-
sweep flow in [`stale-sweeps.md`](classifications/sweep-1a-stale-triaged-draft.md), which acts
on a different action (`stale_draft` → close), not on a
duplicate `draft` proposal.

### Why ≥ 80 chars on comments

The threshold filters out emoji reactions, `+1`, `lgtm`, and
single-sentence acknowledgements while letting through the
typical maintainer critique ("Two things — the migration here
needs a downgrade path, and the new helper duplicates X in
`utils.py`. Converting to draft until those are addressed.").
80 is empirical, not load-bearing; tune with feedback if real
PRs slip through. Reviews are not gated on length because a
review submission is itself a stronger commitment than a free-
form comment — a maintainer who clicks through the review UI
to attach `CHANGES_REQUESTED` has already engaged substantively
even if the body is terse.

### What F6 does not yet cover

Two further signals would strengthen F6 but require new fields
in the batch query:

- A maintainer pushing commits to the author's branch (not
  currently exposed — `commits(last:1)` returns committed-by
  data but not the GitHub login of the pusher in a form the
  query consumes).
- A `convert_to_draft` timeline event authored by a maintainer
  (would require pulling `timelineItems(itemTypes:
  [CONVERT_TO_DRAFT_EVENT])`).

Both are tracked as follow-ups; neither blocks the MVP because
the historical examples that motivated F6 all surface via the
review-or-comment signals F6 already inspects.

---

## Draft vs comment vs ping

All three actions can land violations text on the same PR. The
difference is how they shape the maintainer's queue and the
author's expectations:

- `draft` flips the PR out of the review queue. Says "stop
  requesting review, fix these first, mark ready yourself".
  Right when maintainer review time would be wasted (CI red,
  conflicts, multiple threads, etc.).
- `comment` keeps the PR in the queue. Says "here are the
  issues, continue working, we'll re-look once addressed". Right
  for narrow deterministic issues (static-check failures) the
  author can resolve in one push.
- `ping` is the lightest touch. Says "two specific people, look
  here". Right when the contributor is clearly still iterating
  and dropping back to draft would be discourteous — a full
  violations-list comment would be overkill for "your reviewer
  hasn't seen your latest push yet".

Collaborator-authored PRs (when `authors:collaborators` is
active) always default to `comment` — never `draft`. Collaborators
don't need gentle routing and converting a colleague's PR to
draft is an overreach.

---

## Why fold feedback into the PR body (denoise)

By default (`triage_feedback_channel: pr-body`) the deterministic
quality-violation feedback for `draft`, `comment`, and `close` is
**folded into the PR description** as a managed marker block rather
than posted as a PR comment. See
[`comment-templates.md#body-fold-rendering`](actions/deliver-note.md)
for the mechanism and [`actions.md`](actions/deliver-note.md) for the recipe.

**The motivating problem.** During a design discussion (2026-06-10), maintainers raised that the triage process posts so many comments that it floods maintainer mailboxes — and that the resulting noise causes maintainers to **miss the real human comments** on the PRs they actively track. A comment on a PR notifies every subscriber; across a queue of hundreds of PRs, the routine "here are your violations" comments drown out the conversations that need a human.

**The fix.** A new PR *comment* notifies; editing the PR
*description* does **not**. Folding the same violation text into
the body delivers identical information to the contributor (who
sees it on their PR) and remains fully deterministic, while
producing zero notifications. A maintainer proposed exactly this,
noting it is the technique already used for security issues. The change keeps the whole triage process intact — PRs
that need fixing are still drafted, the criteria are still
surfaced — it only moves the delivery from a notifying channel to
a silent one.

**Why every action folds, not just the violations.** The fold
began with `draft`, `comment` and `close`, the bulk of the noise,
while pings, `request-author-confirmation`, the security-language
warning and the stale-sweep notices kept posting comments because
their purpose is to reach a human. The single-note model
supersedes that: under `pr-body` every contributor-facing action
refreshes the one folded note, so a PR never carries more than one
triage note. The suspicious-changes receipt is the exception — it
is posted on every open PR by a flagged author as a comment.

**Why the note `@`-mentions the author, and only the author.** A
body edit notifies nobody except a freshly added `@`-mention. The
note is a "your move" signal, so it mentions the author exactly
once and assigns them; the author is the only person this skill
ever notifies. Every maintainer handle — the operator credit, a
reviewer named in a nudge — is backtick-quoted and silent, and the
agent-guard `mention` guard blocks any other mention. See
[Golden rules 10 and 11](SKILL.md#contributor-facing-notification-channel).

**Why an idempotent marker block, with metadata.** The block
carries `triaged=` / `head=` in its opening marker so re-triage can
tell, from the body alone, *when* the PR was last triaged and
*whether the author has pushed since* — the exact facts a triage
*comment* used to supply via `createdAt` and "posted after last
commit". Without that, a folded PR would be re-flagged every sweep
— turning a denoise change into a *re-noising* one. The block is
rewritten in place (never appended) so the body holds exactly one
current violation list, and the legacy comment-marker detection is
kept so PRs triaged under the old channel still classify correctly.
See [`viewer_triage_fold_present`](classifications/already-triaged.md).

The behaviour is a project-config switch
([`triage_feedback_channel`](../../../magpie-setup/templates/pr-management-config.md))
defaulting to `pr-body`; an adopter that prefers the notifying
comment channel can set it to `comment` and get the prior
behaviour unchanged.

---

## Merit-discussion exception to `strip-ready-on-downgrade`

The `strip-ready-on-downgrade` hard rule
(see [the decision table](../../../../tools/pr-management/README.md#shared-rules))
otherwise strips `ready for maintainer review` whenever a
regressed PR matches a `deterministic_flag` row with action
`draft` / `comment` / `close`. The
[`merit_discussion_thread_present`](../../../../tools/pr-management/README.md#shared-rules)
exception suspends that strip — and additionally suspends the
draft conversion and the close — when an unresolved
maintainer-opened review thread is present on the PR.

Why this matters:

- The `ready for maintainer review` label exists to attract
  senior eyes. An unresolved maintainer review thread is the
  moment senior eyes are most valuable. Stripping the label
  or pushing the PR back to draft mid-discussion makes the
  PR disappear from the maintainer queue exactly when it
  shouldn't.
- CI red / lint failures / merge conflicts and a live design
  debate are orthogonal axes. A maintainer can usefully weigh
  in on the design discussion even when CI is red — the
  mechanical blockers belong to the author, the design
  question belongs to the maintainers.
- The exception's precondition is deliberately broad — any
  maintainer-opened unresolved review thread counts,
  regardless of body length or when it was opened relative
  to the label-add. A narrower "substantive content"
  heuristic would mis-classify short-but-substantive prompts
  ("is this really the right layer for this change?") as
  trivial and strip the label anyway. Erring toward keeping
  the label is the safer asymmetry: a stale-but-kept label
  costs a maintainer a glance; a stripped label mid-discussion
  costs the discussion its audience.
- Contributor-author unresolved threads do NOT satisfy the
  precondition. The label defers to maintainer judgment, not
  contributor-to-contributor side chatter.

Originating user-scope feedback memory:
`feedback-ready-for-maintainer-review-label`.

---

## Group-level overrides

The interaction loop lets the maintainer override the suggested
action for an entire group (e.g. "these 5 PRs suggested `draft`
but I want to `comment` them instead — the author is actively
fixing"). Mechanics:
[`interaction-loop.md#group-action-override`](interaction-loop.md#group-action-override).
Classification stays the same; only the action switches.

Class overrides are **out of scope**. The maintainer cannot tell
the skill "pretend this PR is `passing`" — they would use
`mark-ready` directly on the PR instead, which is a per-PR
decision the skill never tries to second-guess.

---

## Refuse-to-suggest cases

Rows 6, 7, and 22 in the decision table cover the refuse-to-
suggest cases. The intent of each:

- Row 6 (viewer is the PR author) — triaging your own PR from this skill is unintended. Mutation APIs
  will work but the skill's signal is calibrated for outside contributors — applying it to your own PR
  risks self-drafting. Skip with a one-line note and let the maintainer use the action verbs directly.
- Row 7 (too fresh) — a PR created in the last 30 minutes hasn't had time for CI to finish. Flagging it
  on checks that simply haven't run yet would read as the bot pouncing on new contributors. Skip with a
  "too fresh" note.
- Row 22 (data inconsistency) — when the PR's data looks
  inconsistent (rollup says SUCCESS but `failed_checks` is non-
  empty, or similar), surface the inconsistency to the
  maintainer with a one-line note and skip. Data anomalies
  usually mean GitHub hasn't fully settled the rollup yet; a
  refresh on the next page typically clears it. Do not guess.

---

## Reason strings — tone and discipline

The reason goes in front of a maintainer who is already
frustrated; do not add to the frustration. Concrete rules:

- Lead with the signal that fired the rule (failing-check
  category, reviewer login, age, flagged-PR count).
- End with the proposal verb (suggest rerun / draft / close /
  comment / ping / mark-ready).
- No editorialising, no scare quotes, no emoji, no LLM-generated
  prose.

The full surface area is the templates in
[`classify-and-act.md#reason-template-rules`](../../../../tools/pr-management/README.md#shared-rules).
Anything beyond that is drift.

---
