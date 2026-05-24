<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Actions

Exact recipes for every mutation the skill can execute. Every
action in this file assumes:

- the maintainer has confirmed it,
- the PR's `head_sha` has been re-checked against the value
  captured in Step 1 and matches (optimistic lock — see
  [`interaction-loop.md#optimistic-lock`](interaction-loop.md)),
- the action's comment (if any) has been previewed to the
  maintainer from the appropriate template in
  [`comment-templates.md`](comment-templates.md).

All mutations go through **`gh`**, never through raw `curl` /
`requests`. `gh` carries the maintainer's authenticated token
and retries transient failures correctly.

---

## `draft` — convert to draft and post violations comment

Two mutations, **sequence matters** — convert first, then post
the comment. Posting the comment before converting leaves the
comment on a non-draft PR if the conversion fails.

```bash
# 1. Convert to draft (`gh pr ready <N> --undo` is the CLI
#    equivalent of the GraphQL `convertPullRequestToDraft` mutation).
gh pr ready <N> --repo <repo> --undo

# 2. Post the violations comment
gh pr comment <N> --repo <repo> --body-file /tmp/pr-<N>-draft-body.md
```

Build `/tmp/pr-<N>-draft-body.md` from the `draft` template in
[`comment-templates.md`](comment-templates.md#draft-comment).
Write the file, `gh pr comment --body-file`, then delete the
temp file in the same turn. Body-file mode avoids shell-escape
issues for long markdown bodies.

On the `gh pr ready --undo` failing: surface the error, **do
not** post the comment. A comment that says "converted to draft"
on a still-open PR is a worse state than no comment at all.

### If the PR carries `ready for maintainer review`

The PR bypassed F4 because of post-label regression (rebase /
push re-introduced a deterministic failure — see
[`strip-ready-on-downgrade`](classify-and-act.md#hard-rules-cross-cutting-the-table)).

**Branch on the merit-discussion exception.** Before mutating,
evaluate
[`merit_discussion_thread_present`](classify-and-act.md#merit_discussion_thread_present)
on the PR.

**Case A — no merit discussion present** (the strip-and-draft
default). Strip the label as the **first** mutation, before
converting to draft, so the queue position is corrected even
if a later step fails:

```bash
# 0. Remove the now-stale ready-for-review label (idempotent —
#    a 422 "Label does not exist on this issue" is benign; log
#    and continue).
gh pr edit <N> --repo <repo> --remove-label "ready for maintainer review"

# 1. Convert to draft
gh pr ready <N> --repo <repo> --undo

# 2. Post the violations comment
gh pr comment <N> --repo <repo> --body-file /tmp/pr-<N>-draft-body.md
```

If step 0 fails with anything other than the benign "label not
applied" / "label not found" response, surface the error and
proceed to the draft + comment anyway — the label-removal
failure is a soft signal (the maintainer may need to clean up
manually), but stranding the PR in a half-state would be
worse. The maintainer-facing preview should note when step 0
will run so the proposal is honest about both state changes.

**Case B — merit discussion present** (per the exception in
[`strip-ready-on-downgrade`](classify-and-act.md#hard-rules-cross-cutting-the-table)).
Skip step 0 (label stays) and step 1 (PR stays out of draft).
Post only the violations comment:

```bash
# 1. Post the violations comment (label stays; PR stays open).
gh pr comment <N> --repo <repo> --body-file /tmp/pr-<N>-draft-body.md
```

The maintainer-facing preview MUST surface that the merit
discussion was detected and that the action is being
de-escalated from `draft` to `comment-only` for this reason
— include the URLs of the maintainer-opened unresolved review
thread(s) that triggered the exception so the maintainer can
sanity-check the call. The violations comment body is
unchanged from Case A; it informs the author that mechanical
issues remain even though the discussion is what's keeping
the label on.

### If the PR is already a draft

Skip the `gh pr ready --undo` step. Post only the comment. The
decision table in [`classify-and-act.md`](classify-and-act.md)
should have chosen `comment` instead in this case, but
double-check here as a guard. The label-removal step (when
applicable) still runs first.

### Collaborator-authored PRs

Do not draft a collaborator's PR. If somehow the action landed
as `draft` for a collaborator, fall back to `comment` with the
same body — no draft flip. The label-removal step (when
applicable) still runs.

---

## `comment` — post violations / stale-review / ping comment

A single mutation. The template depends on the upstream
classification:

| Upstream | Body source |
|---|---|
| `deterministic_flag` with action `comment` | [`comment-templates.md#comment-only`](comment-templates.md) |
| `stale_review` with action `ping` | [`comment-templates.md#review-nudge`](comment-templates.md) |
| `deterministic_flag` (explicit ping action) | [`comment-templates.md#reviewer-ping`](comment-templates.md) |

```bash
gh pr comment <N> --repo <repo> --body-file /tmp/pr-<N>-comment.md
```

For a `ping` action, `@`-mention every stale reviewer plus the
PR author in the body — do not let the ping go without naming
the people it's for.

### If the PR carries `ready for maintainer review` (deterministic_flag only)

When the upstream classification is `deterministic_flag` and the
PR carries the label (regression bypass of F4 — see
[`strip-ready-on-downgrade`](classify-and-act.md#hard-rules-cross-cutting-the-table)),
strip the label **before** posting the comment — **unless**
[`merit_discussion_thread_present`](classify-and-act.md#merit_discussion_thread_present)
holds, in which case the label stays and only the comment is
posted.

```bash
# 0. Remove the now-stale ready-for-review label.
#    SKIP this step when merit_discussion_thread_present holds.
gh pr edit <N> --repo <repo> --remove-label "ready for maintainer review"

# 1. Post the violations comment
gh pr comment <N> --repo <repo> --body-file /tmp/pr-<N>-comment.md
```

A 422 "label not applied" / "label not found" is benign — log
and continue with the comment.

This applies only to the `deterministic_flag` → `comment`
branch (typically the collaborator-mode fallback from `draft`,
or static-check-only failures). `stale_review` and explicit
`ping` actions do NOT strip the label — those are transient
signals and the ready-for-review queue position is still valid
information for the reviewer.

When the merit-discussion exception applies, the
maintainer-facing preview MUST surface that step 0 is being
skipped and quote the URL(s) of the maintainer-opened
unresolved review thread(s) that triggered the exception.

---

## `close` — close with comment and quality-violations label

Three mutations. Comment first (so the contributor sees the
reasoning), then close, then label. Closing without commenting
is perceived as hostile — do not do it.

```bash
# 1. Post the close comment
gh pr comment <N> --repo <repo> --body-file /tmp/pr-<N>-close.md

# 2. Close the PR
gh pr close <N> --repo <repo>

# 3. Add the quality-violations label (if the label exists on the repo)
gh pr edit <N> --repo <repo> --add-label "closed because of multiple quality violations"
```

Body template: [`comment-templates.md#close`](comment-templates.md).

If the label is missing (per `prerequisites.md#3`), skip the
label step with a one-line warning; the close + comment is
still valid.

`close` is always a **per-PR** action, never batched. Even
inside a `close` group, the maintainer confirms each PR
individually — a wrongly-closed PR is the hardest mistake to
recover from.

### If the PR carries `ready for maintainer review` and a merit discussion is in flight

When the PR carries `ready for maintainer review` AND
[`merit_discussion_thread_present`](classify-and-act.md#merit_discussion_thread_present)
holds, the
[`strip-ready-on-downgrade`](classify-and-act.md#hard-rules-cross-cutting-the-table)
exception applies: **skip step 2** (do not close the PR) and
**do not strip the ready-for-maintainer-review label**. Steps
1 and 3 still run — the close comment surfaces the
queue-pressure reasoning, and the quality-violations label
records that the PR was flagged. The PR remains open with
both labels, surfaced for human review.

The maintainer-facing preview MUST surface that step 2 is
being skipped and quote the URL(s) of the maintainer-opened
unresolved review thread(s) that triggered the exception.
Closing a PR with an active maintainer review discussion is
strictly more destructive than the queue-pressure problem
`close` exists to solve — a human maintainer must make that
call, not the skill.

---

## `mark-ready` — add `ready for maintainer review` label

**Mandatory pre-mutation check.** Before adding the label, the
implementation MUST verify there are no GitHub Actions workflow
runs awaiting approval for the PR's head SHA. The classifier's
rollup-state and real-CI-context checks
(see [`classify-and-act.md#real-ci-guard`](classify-and-act.md)) are a
first line of defense; this REST check is the authoritative
second line that catches the case where the classifier was
right at fetch time but a new push or a freshly-indexed run
appeared since.

Reason: a PR whose real CI is held in `action_required` can have
`statusCheckRollup.state == SUCCESS` from fast bot checks
(`Mergeable`, `WIP`, `DCO`, `boring-cyborg`) while `Tests`,
`CodeQL`, and `Check newsfragment PR number` have not run.
Labelling such a PR "ready for maintainer review" is premature —
the maintainer queue fills with PRs whose CI has not actually
executed.

```bash
# Pre-check: index action_required runs at the head SHA.
# Note: runs awaiting approval are returned as `status: "completed"`
# with `conclusion: "action_required"`. The query parameter
# `?status=action_required` matches no runs and would silently
# return an empty result — post-filter on `conclusion` instead.
head_sha=$(gh api "repos/<owner>/<repo>/pulls/<N>" --jq '.head.sha')
pending=$(gh api "repos/<owner>/<repo>/actions/runs?head_sha=${head_sha}&per_page=20" \
  --jq '[.workflow_runs[] | select(.conclusion == "action_required")] | length')
if [ "$pending" -gt 0 ]; then
  echo "refuse mark-ready: <N> has ${pending} workflow run(s) awaiting approval at ${head_sha}" >&2
  # Reclassify: this PR is really pending_workflow_approval, route accordingly.
  exit 2
fi

# Guard passed — apply the label.
gh pr edit <N> --repo <repo> --add-label "ready for maintainer review"
```

When the guard refuses, the implementation should **reclassify
the PR as `pending_workflow_approval`** (see
[`classify-and-act.md#decision-table`](classify-and-act.md), row 1) and
route to the workflow-approval flow rather than silently dropping
the mutation.

No comment is posted — the label is the signal. If the label
doesn't exist (per `prerequisites.md#3`), stop and surface the
error; this is the only action of the skill whose sole purpose
*is* the label, so there's no graceful degradation.

---

## `promote-bot-draft` — convert a bot-authored draft and label it ready

The action behind [Step 0.5 of `SKILL.md`](SKILL.md#step-05--promote-bot-authored-draft-prs).
Two mutations bundled per PR: convert draft → non-draft
(`gh pr ready`) and add the `ready for maintainer review`
label.

Inherits the workflow-approval guard from
[`mark-ready`](#mark-ready--add-ready-for-maintainer-review-label)
verbatim — Golden rule 1b in [`SKILL.md`](SKILL.md) applies
to every code path that adds the label, including this one.

```bash
# Pre-check: same action_required index lookup as mark-ready.
head_sha=$(gh api "repos/<owner>/<repo>/pulls/<N>" --jq '.head.sha')
pending=$(gh api "repos/<owner>/<repo>/actions/runs?head_sha=${head_sha}&per_page=20" \
  --jq '[.workflow_runs[] | select(.conclusion == "action_required")] | length')
if [ "$pending" -gt 0 ]; then
  echo "refuse promote-bot-draft: <N> has ${pending} workflow run(s) awaiting approval at ${head_sha}" >&2
  # Reclassify the PR as pending_workflow_approval; the maintainer
  # handles it via the approve-workflow flow rather than promoting blind.
  exit 2
fi

# Mutation 1 — flip draft to ready-for-review.
gh pr ready <N> --repo <repo>

# Mutation 2 — add the ready-for-maintainer-review label.
gh pr edit <N> --repo <repo> --add-label "ready for maintainer review"
```

Order matters: `gh pr ready` first, then the label add. If
`gh pr ready` fails (PR is no longer a draft, was closed, the
bot pushed a new commit and the head SHA moved) the action stops
before labelling — the PR is no longer in the bot-draft
category and should be re-classified by the normal flow on the
next run. If the label step fails after a successful ready
toggle, do **not** roll back: the ready toggle is still a
maintainer-visible improvement; log the label-add failure for
the session summary so the maintainer can retry next sweep.

No comment is posted. The bot's own commit message plus the
`ready for maintainer review` label are sufficient signal — a
contributor-facing footer would be misdirected for a bot author
that won't read it.

---

## `request-author-confirmation` — ask the PR author whether feedback is addressed

Single mutation. Used when the only `deterministic_flag` signal
is unresolved review threads **and** the
[`unresolved_threads_only_likely_addressed`](classify-and-act.md#unresolved_threads_only_likely_addressed)
sub-flag is true (the author has engaged with every unresolved
thread via a post-comment commit or an in-thread reply).

The action does **not** add the `ready for maintainer review`
label and does **not** `@`-mention the original reviewers.
Those steps belong to the second leg of this two-sweep flow,
gated on an explicit author confirmation
([row 14a](classify-and-act.md#decision-table) →
[`mark-ready`](#mark-ready--add-ready-for-maintainer-review-label)).

```bash
gh pr comment <N> --repo <repo> --body-file /tmp/pr-<N>-request-author-confirmation.md
```

Body template:
[`comment-templates.md#request-author-confirmation`](comment-templates.md).

The body `@`-mentions the PR author only, and **must** include
the canonical marker string `ready for maintainer review
confirmation` verbatim — that string is what
[`viewer_confirmation_request_present`](classify-and-act.md#viewer_confirmation_request_present)
searches for on subsequent sweeps to detect that a confirmation
request is in flight. Do not paraphrase the marker.

### Why no label, no reviewer mention

The classifier's signal that fired this action is *engagement*
(post-review commits, in-thread author replies), not
*resolution*. A post-review commit does not guarantee the
commit addresses the specific thread; an in-thread reply does
not guarantee the reply resolves it. Adding the label and
mentioning reviewers off the engagement signal alone pushes a
notification framed as a stronger claim than the underlying
evidence supports. The two-sweep gate — ask the author, wait
for their reply, then promote — moves the resolution check to
the only person who reliably knows: the author.

The label is also intentionally absent at this stage so that
the PR does not enter the maintainer review queue until after
the author has confirmed. Reviewers are reached via the queue,
not via direct `@`-mention from the bot — see
[`rationale.md`](rationale.md) for the longer argument.

### What happens next

- Author replies → next sweep classifies the PR as
  [`author_confirmation_received`](classify-and-act.md#author_confirmation_received)
  and proposes [`mark-ready`](#mark-ready--add-ready-for-maintainer-review-label).
  The triaging maintainer reads the author's reply alongside
  the proposal and confirms (or overrides to `skip` / `ping`
  if the reply is non-affirmative).
- Author silent → on the cooldown sweep, the PR matches the
  [stale author-confirm-request sweep](stale-sweeps.md#sweep-5--stale-author-confirm-request),
  which proposes a plain `ping` (or `skip`).
- Author pushes a new commit before replying → the
  [`viewer_confirmation_request_present`](classify-and-act.md#viewer_confirmation_request_present)
  precondition fails (the confirmation request now predates the
  new head commit) and the PR drops back to row 14c / 15 for
  re-classification against the new state.

### Failure handling

A failed `gh pr comment` (network blip, rate-limit) is non-
destructive — surface the error and let the maintainer retry on
the next sweep. No partial state to clean up.

### Falling back to plain `ping`

If the post-confirmation drill-in (e.g. the maintainer pulled
the PR out of the group with `[P]ick`) reveals that the threads
are *not* actually addressed (the author's engagement was a
clarifying question or a partial fix), the maintainer can
override the action to `ping`. The override posts the regular
[`reviewer-ping`](comment-templates.md#reviewer-ping) body
instead. See
[`interaction-loop.md#group-action-override`](interaction-loop.md).

---

## `rerun` — rerun failed CI workflow runs

Multi-step. We need to find the workflow runs for this PR's
head SHA, then rerun the failed ones.

```bash
# 1. List runs for this SHA
gh run list --repo <repo> --commit <head_sha> \
  --limit 50 \
  --json databaseId,name,status,conclusion

# 2. For each run where conclusion == "failure", rerun failed jobs
gh run rerun <run_id> --repo <repo> --failed
```

`--failed` reruns only the failed jobs in that run, which is
what the original `breeze` tool does. If you use plain
`gh run rerun` (no `--failed`) it reruns the whole workflow —
expensive and unnecessary.

### In-progress runs

If every failed run has `status != completed`, there's nothing
to rerun via `--failed`. Fall back to cancelling and restarting
the in-progress runs:

```bash
gh run list --repo <repo> --commit <head_sha> --status in_progress \
  --json databaseId --jq '.[].databaseId' |
  while read run_id; do
    gh run cancel "$run_id" --repo <repo>
    gh run rerun "$run_id" --repo <repo>
  done
```

Use this only when the `--failed` path turned up nothing —
cancelling in-progress runs discards current work.

### No runs found at all

Surface to the maintainer: "No workflow runs found for this
SHA — the PR may need a push or a rebase to re-trigger CI".
Fall through to suggesting `rebase` for next time.

---

## `rebase` — update the PR branch with base

**Never attempt this action when `mergeable == CONFLICTING`.**
GitHub's update-branch endpoint does a side-merge of the base
branch into the PR head; the merge fails deterministically
when the conflicts can't be auto-resolved, returns `422`, and
burns a round-trip. The skill empirically hit this on every
conflicting PR it tried during testing on `<upstream>`.
The decision table in [`classify-and-act.md`](classify-and-act.md)
routes CONFLICTING PRs to `draft` (row 9) instead — if a `rebase`
action arrives here despite that, treat the conflict state itself
as a hard refuse.

Pre-flight guard:

```bash
merg=$(gh api graphql -F n=<N> -f query='
  query($n: Int!) {
    repository(owner:"<owner>",name:"<repo>") {
      pullRequest(number: $n) { mergeable }
    }
  }' --jq '.data.repository.pullRequest.mergeable')
if [ "$merg" = "CONFLICTING" ]; then
  echo "refuse: CONFLICTING — route to draft instead" >&2
  exit 2
fi
```

When the guard passes, single mutation via `gh`:

```bash
gh pr update-branch <N> --repo <repo>
```

This requires `gh` 2.20+. On older `gh`, fall back to:

```bash
gh api -X PUT repos/<owner>/<repo>/pulls/<N>/update-branch
```

GitHub replies with `202 Accepted` for a successful update — it
merges (or rebases, per repo settings) the base into the PR
branch. If the call still 422s despite a non-CONFLICTING
`mergeable` state (rare — usually means GitHub recomputed the
mergeable state between our guard and the call), surface the
error and **do not retry**; route to `draft` with the merge-
conflicts violation. Never burn successive round-trips on the
same PR in one session.

No comment is posted for `rebase` by default. The contributor
will see the merge commit (or rebased branch) in their PR.

---

## `ping` — nudge stale review / unresolved thread

Alias for `comment` with the `review-nudge` or `reviewer-ping`
body template, but distinct as an action so the maintainer can
confirm it separately from the generic `comment` action.

```bash
gh pr comment <N> --repo <repo> --body-file /tmp/pr-<N>-ping.md
```

**Pick the body variant deliberately — default to pinging the
author.** The skill has two body families:

- [`comment-templates.md#review-nudge`](comment-templates.md) —
  for `stale_review` (a `CHANGES_REQUESTED` review with newer
  author commits and no follow-up).
- [`comment-templates.md#reviewer-ping`](comment-templates.md) —
  for `deterministic_flag` → `ping` (unresolved review thread
  from a collaborator).

Each family has an **author-primary** variant (the default) and
a **reviewer-re-review** variant. Before drafting, inspect the
review thread + the post-review diff using the decision rule in
[`comment-templates.md#review-nudge`](comment-templates.md). Use
the reviewer-re-review variant **only** when that inspection
confirms the feedback has been addressed in a post-review
commit or resolved with an author reply in-thread; otherwise
stay with the author-primary variant so the to-do stays on the
correct desk.

The template **must** include `@`-mentions of every stale
reviewer *and* the PR author when using the reviewer-re-review
variant. In the author-primary variant, mention the author
first (they're the one who needs to act) and list the reviewers
as `<reviewers>` so they see the notification but the
responsibility is clearly on the author.

---

## `approve-workflow` — approve pending CI runs for first-time contributor

Two steps. **Inspect the diff first** — see
[`workflow-approval.md`](workflow-approval.md) for the safety
protocol. Only after the maintainer confirms the diff looks
non-malicious, **re-list the pending runs at action time** (the
per-page `action_required` index built during fetch may be stale
— another maintainer may have approved between fetch and now —
and the optimistic-lock pattern below catches the no-op race
without burning a useless mutation):

```bash
# Re-list pending workflow runs for this PR at action time.
# Runs awaiting approval are returned as `status: "completed"` with
# `conclusion: "action_required"` — `?status=action_required` matches
# none of them. Post-filter on `conclusion` to enumerate the real set.
ids=$(gh api "repos/<owner>/<repo>/actions/runs?head_sha=<head_sha>&per_page=20" \
        --jq '.workflow_runs[] | select(.conclusion == "action_required") | .id')

if [ -z "$ids" ]; then
  # Race: pending runs were approved between fetch and now (another
  # maintainer, or auto-approval). Skip silently — the desired state
  # ("CI is allowed to run for this contributor") is already true.
  # Surface a one-line note to the maintainer so the no-op is visible.
  echo "approve-workflow: no pending runs found at <head_sha> — already approved by someone else" >&2
  exit 0
fi

while read -r run_id; do
  [ -z "$run_id" ] && continue
  gh api -X POST "repos/<owner>/<repo>/actions/runs/${run_id}/approve"
done <<< "$ids"
```

The optimistic-lock pattern is the same one
[`mark-ready`](#mark-ready--add-ready-for-maintainer-review-label)
uses (Golden rule 1b in [`SKILL.md`](SKILL.md)) — read the
authoritative state immediately before mutating, exit cleanly
if the desired state is already in place. Without it, a sweep
that classified at T0 and acts at T0 + minutes (after the
maintainer reviewed the diff) silently surfaces "exit=0, out=
empty" with no guidance on whether the approval landed or
nothing was there to approve in the first place.

No comment is posted for `approve-workflow`. Approval is
invisible to the contributor except for CI now running, which
is what they wanted.

### If the maintainer flagged suspicious

Route to `flag-suspicious` below — do **not** approve.

---

## `flag-suspicious` — close all open PRs by the author

The heaviest action in the skill. Reserved for PRs whose diff
contains clear tampering indicators (secret exfiltration, CI
pipeline modifications, `.env` writes, curl-to-shell patterns
introduced outside legitimate tool updates). See
[`workflow-approval.md#what-counts-as-suspicious`](workflow-approval.md)
for the signal list.

Scope: close **all** currently-open PRs authored by the
suspicious author, attach the `suspicious changes detected`
label, post a short explanatory comment. This is the action the
original `breeze` tool performed on the "flag as suspicious"
path.

```bash
# 1. List open PRs by the author
gh pr list --repo <repo> --author <author_login> --state open \
  --json number --jq '.[].number'

# 2. For each PR, in parallel — close + label + comment
for pr in $PR_NUMBERS; do
  gh pr comment "$pr" --repo <repo> --body-file /tmp/pr-<pr>-suspicious.md
  gh pr close "$pr" --repo <repo>
  gh pr edit "$pr" --repo <repo> --add-label "suspicious changes detected"
done
```

Body template: [`comment-templates.md#suspicious-changes`](comment-templates.md).

The comment is deliberately short and non-accusatory — the
action is the message, the comment is just the receipt.

**Require per-author confirmation**, not per-PR: the maintainer
confirms once for "close all N PRs by @<author>", then the
skill executes the whole set. This is the one time batch
execution is appropriate for destructive actions, because the
whole point is "this author's activity is being treated as a
unit". Sending N individual confirm prompts would dilute the
decision.

---

## `strip-ready-label` — remove the ready-for-review label, no comment

Used by [Sweep 4a — branch healthy → strip label](stale-sweeps.md#4a--branch-healthy--strip-label).
One mutation, no comment. (The rotted-branch sibling
[Sweep 4b](stale-sweeps.md#4b--branch-rotted--propose-close)
uses `close` instead, not this action.)

```bash
# Remove the now-stale ready-for-review label (idempotent —
# a 422 "Label does not exist on this issue" is benign; log
# and continue).
gh pr edit <N> --repo <repo> --remove-label "ready for maintainer review"
```

The label string is read from
[`<project-config>/pr-management-config.md → ready_for_maintainer_review_label`](../../../projects/_template/pr-management-config.md);
do not hard-code it. The same `gh` recipe is used by the
"strip-on-downgrade" hook inside `draft` and `comment`
(`actions.md` §[draft](#draft--convert-to-draft-and-post-violations-comment) /
§[comment](#comment--post-violations--stale-review--ping-comment)),
but those flows additionally convert to draft / post a
comment. The `strip-ready-label` action is **only** the
label-removal step — no other mutation, no comment.

### Why no comment

The PR already carries an unanswered maintainer comment (that
is the trigger condition; see Sweep 4a). Posting a second
contributor-facing comment would either duplicate the
maintainer's existing ask or race the normal-queue re-triage
that may run on the next sweep. Removing the label silently
is the most conservative move; the maintainer can re-add the
label in one click if the strip was unwarranted.

### Failure handling

- 422 "Label does not exist on this issue" — benign, log and
  treat the action as successful (the desired end state is
  already in place).
- 404 / network error — surface to the maintainer with the PR
  number, do not retry silently. The next sweep run will
  re-evaluate.
- Anything else — surface and stop the batch (consistent with
  the `gh pr edit --remove-label` failure handling in `draft`).

### Order-of-operations

One step. No comment to sequence against.

---

## Order-of-operations recap for destructive actions

For every action that includes a comment, post the comment
**before** the state change that hides it:

| Action | Order |
|---|---|
| `draft` | (*if F4-regression: remove ready-for-review label*) → convert to draft → post comment |
| `comment` | (*if F4-regression on `deterministic_flag`: remove ready-for-review label*) → post comment |
| `close` | post comment → close → label |
| `flag-suspicious` | post comment → close → label *(per PR in the batch)* |
| `mark-ready` | label only |
| `request-author-confirmation` | post comment only (no label) |
| `strip-ready-label` | remove-label only (no comment) |
| `rerun` | rerun (no comment) |
| `rebase` | update-branch (no comment) |
| `ping` | post comment |
| `approve-workflow` | approve (no comment) |

The `draft` case is the exception to "comment before state
change" because drafts still show comments fine. The `close`
case must be comment-first because closed-PR comments are
visible but the "PR closed" notification beats the comment
otherwise and the contributor reads the wrong order.

---

## Batching execution

When the maintainer accepts `[A]ll` on a group:

- Issue the mutations **in parallel** across PRs using parallel
  tool calls. `gh` is thread-safe from separate processes and
  the rate limit for mutations is per-request, not per-second
  batch.
- Cap parallelism at **5 concurrent mutations** to keep
  spurious errors from swamping the maintainer's screen.
- For `close` groups, the cap is **1** (sequential) even on
  `[A]ll` — we still walk them one-at-a-time, just without the
  per-PR confirm.

Update the session cache after each batch completes, not after
each mutation — a half-completed cache is a confusing debugging
artifact.

---

## Error handling

Mutations can fail for a handful of reasons. Handle them
specifically, not generically:

| Error | Handling |
|---|---|
| `HTTP 401/403` on a previously-working token | Stop the session, surface "token expired or permissions changed" |
| `HTTP 422` with "PR is already closed" | Log and continue (someone else closed it between our fetch and mutate) |
| `HTTP 422` with "label already applied" | Log and continue (idempotent) |
| `HTTP 404` on a PR number | Log and continue (PR was deleted — rare) |
| `HTTP 5xx` | Retry once after 2 seconds; on second failure, surface and continue with next PR |
| GraphQL error with `RATE_LIMITED` / `X-RateLimit-Remaining: 0` | Stop, surface remaining-quota info, let the maintainer decide whether to continue |

Do not wrap the entire session in a blanket `except`. Let
bugs surface.
