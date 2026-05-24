<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Comment templates

Every comment the skill posts comes from this file. The
templates exist to keep the tone consistent across the project
and to make the `Pull Request quality criteria` marker show up
in the same place on every triage comment so
the `already_triaged` rows in [`classify-and-act.md#decision-table`](classify-and-act.md#decision-table) (rows 3–4) can find them.

Placeholders:

- `<author>` — PR author's GitHub login (without `@` — the
  template adds it)
- `<violations>` — the rendered violations list (see
  [`#violations-rendering`](#violations-rendering))
- `<base>` — PR base branch name (`main`, `v3-1-test`, …)
- `<commits_behind>` — integer
- `<flagged_count>` — number of currently-flagged PRs by this
  author (for the `close` template)
- `<reviewers>` — space-separated `@login` mentions. **Use in
  reviewer-re-review variants and `mark-ready-with-ping` only**
  — those templates address the reviewer as the next-action
  recipient, so `@`-pinging them is appropriate.
- `<reviewer_logins>` — comma-separated backtick-quoted logins
  (e.g. `` `phanikumv` ``, `` `phanikumv`, `eladkal` ``) —
  **no `@`-pings**. Use in author-primary templates
  (`request-author-confirmation`, `reviewer-ping` author-primary,
  `review-nudge` author-primary) where the only addressee is the
  PR author. The reviewer is mentioned for context; an `@`-ping
  would needlessly notify them when the next action is on the
  author. See the [Reviewer-mention policy](#reviewer-mention-policy)
  section below.
- `<days_since_triage>` — integer, for the stale-draft close
  comment

All templates use the canonical link to the quality-criteria
document (read from `<project-config>/pr-management-triage-comment-templates.md
→ <quality_criteria_url>`):

```markdown
[Pull Request quality criteria](<quality_criteria_url>)
```

Do not paraphrase this link — the literal text "Pull Request
quality criteria" is the triage-comment marker the skill
searches for when classifying already-triaged PRs. Changing the
anchor text breaks the re-triage skip logic.

---

## Reviewer-mention policy

When a comment's only addressee is the PR author (the
`request-author-confirmation`, `reviewer-ping` author-primary,
and `review-nudge` author-primary templates), the body references
the reviewer **without** `@`-mentioning them. The default
`<reviewers>` placeholder renders as `@login` and is appropriate
when the reviewer is one of the message's addressees (e.g. the
reviewer-re-review variants and `mark-ready-with-ping`). In
author-primary templates we use a different placeholder,
`<reviewer_logins>`, that renders the same logins **as
backtick-quoted code** (e.g. `` `phanikumv` ``,
`` `phanikumv`, `eladkal` ``) — recognisable as a GitHub handle
without producing a notification.

The policy: a reviewer is mentioned for context; an `@`-ping is
only appropriate when the reviewer is the next person whose
action we are asking for. Author-primary templates additionally
tell the author what to do *when* they're ready (mark threads
resolved + `@`-mention the reviewer themselves), so the ping
happens — driven by the author, after they've engaged — rather
than by the bot.

| Placeholder | Renders as | Use in |
|---|---|---|
| `<reviewers>` | `@login [, @login ...]` | reviewer-re-review variants, `mark-ready-with-ping` |
| `<reviewer_logins>` | `` `login` [, `login` ...] `` (no `@`) | `request-author-confirmation`, `reviewer-ping` (author-primary), `review-nudge` (author-primary) |

---

## AI-attribution footer

**Every contributor-facing template below ends with this
footer.** It calibrates the contributor's trust in the comment
(AI-drafted, may be wrong), reassures them that a human
maintainer is the real gate, and links to the documented
rationale for the two-stage process so the message is not just
a disclaimer but a pointer to the project's policy.

`<ai_attribution_footer>` expands to exactly:

```markdown
---

_Note: This comment was drafted by an AI-assisted triage tool and may contain mistakes. Once you have addressed the points above, an <PROJECT> maintainer — a real person — will take the next look at your PR. We use this [two-stage triage process](<two_stage_triage_rationale_url>) so that our maintainers' limited time is spent where it matters most: the conversation with you._
```

(`<quality_criteria_url>`, `<two_stage_triage_rationale_url>`, and
`<PROJECT>` are read from
`<project-config>/pr-management-triage-comment-templates.md`.)

Rules for the footer:

- **Always include it** on every contributor-facing comment the
  skill posts — `draft`, `comment-only`, `close`,
  `review-nudge`, `reviewer-ping`, `request-author-confirmation`,
  `stale-draft-close`, `inactive-to-draft`,
  `stale-workflow-approval`. The only exception is the
  `suspicious-changes` template, which is short, operationally
  sensitive, and already directs the contributor to maintainers
  on Slack — adding the footer there would dilute the signal.
- **Do not paraphrase it.** Post the block verbatim. If the
  wording needs to change, update this section and propagate —
  do not drift per-template.
- **Keep the link to the rationale anchor** (`#why-the-first-
  pass-is-automated`). That section of the contributing doc is
  where the project explains why the first pass is automated
  and why that frees maintainers' time for human conversation.
  Changing the anchor text breaks the link.
- **Place it after all other body content, before any trailing
  blank lines.** The horizontal rule (`---`) separates it from
  the body so GitHub renders it as a clear footer.
- **The footer is italicised in one block** to read as meta-
  commentary rather than part of the primary message.

---

## Security-language comment

*(`security_language_signal` — security-disclosure warning)*

Used when the action is `comment` for a
`security_language_signal` classification (see
[`classify-and-act.md` row 7a](classify-and-act.md#decision-table)).

`<security_matches>` is a bullet list, one item per match, in the
form: `- [location]: "[matched text]"` where location is one of
`PR title`, `PR body`, or `commit <SHA7>`.

```markdown
@<author> This PR's title, body, or commit messages contain language that may indicate a security fix. Under the [ASF vulnerability-handling process for committers](https://www.apache.org/security/committers.html), references to the security nature of a fix must not appear in public-facing content until the CVE is formally announced:

> _"Messages associated with any commits should not make any reference to the security nature of the commit."_

**Matched text:**

<security_matches>

**To move forward, please do one of the following:**

**(a) Neutralise the language** — edit the PR title and body to remove security references, and amend your commit messages so they describe the change without mentioning vulnerabilities. Then reply here to let us know it's done.

**(b) Confirm disclosure is complete** — if the CVE for this fix is already publicly announced, reply with a link to the announcement. A maintainer will then proceed with normal review.

If you haven't already followed the [ASF security reporting process](https://www.apache.org/security/committers.html), please report the vulnerability privately to `security@apache.org` (or the project's security list) before continuing.

[Pull Request quality criteria](<quality_criteria_url>)

<ai_attribution_footer>
```

---

## Draft comment

*(`draft` — convert-to-draft comment)*

Used when the action is `draft` (see
[`actions.md#draft`](actions.md)).

```markdown
@<author> Converting to **draft** — this PR doesn't yet meet our [Pull Request quality criteria](https://github.com/<upstream>/blob/main/contributing-docs/05_pull_requests.rst#pull-request-quality-criteria).

<violations>

<rebase_note_if_needed>

See the linked criteria for how to fix each item, then mark the PR "Ready for review". This is **not** a rejection — just an invitation to bring the PR up to standard. No rush.

<ai_attribution_footer>
```

`<rebase_note_if_needed>` is present **only** when
`commits_behind > 50`:

```markdown
> **Note:** Your branch is **<commits_behind> commits behind `<base>`**. Please rebase and push again to get up-to-date CI results.
```

---

## Comment only

*(`comment-only` — post-without-drafting comment)*

Used when the action is `comment` for a `deterministic_flag`
classification.

```markdown
@<author> A few things need addressing before review — see our [Pull Request quality criteria](https://github.com/<upstream>/blob/main/contributing-docs/05_pull_requests.rst#pull-request-quality-criteria).

<violations>

<rebase_note_if_needed>

No rush.

<ai_attribution_footer>
```

Same shape as the `draft` variant minus the "Converting to
draft" opener and the "not a rejection" reassurance (nothing
is being drafted/closed here, so it doesn't apply). The
classification marker ("Pull Request quality criteria" link
text) is still present — re-triage logic recognises both.

---

## Close

*(`close` — close-with-comment)*

Used when the action is `close` (deterministic flags, author
has >3 flagged PRs) — see
[`actions.md#close`](actions.md).

```markdown
@<author> Closing — this PR has multiple violations of our [Pull Request quality criteria](https://github.com/<upstream>/blob/main/contributing-docs/05_pull_requests.rst#pull-request-quality-criteria).

<violations>
- :x: **Multiple flagged PRs**: <flagged_count> of your PRs are currently flagged for quality issues. Please focus on those before opening new ones.

This is **not** a rejection — you're welcome to open a new PR addressing the issues above. No rush.

<ai_attribution_footer>
```

The "Multiple flagged PRs" line is appended to the violations
list before rendering — do not re-render `<violations>` without
it. If `flagged_count <= 3` (which shouldn't happen on this
template per [`classify-and-act.md`](classify-and-act.md) row 8),
render the close comment without this extra line.

---

## Review nudge

*(`review-nudge` — stale `CHANGES_REQUESTED` ping)*

Used when the action is `ping` on a `stale_review`
classification.

**Strongly prefer pinging the author** to address the
outstanding feedback. The skill may only flip to pinging the
reviewer when it has **inspected the review thread + the
commits pushed after the review** and judged that the feedback
was already addressed but never re-reviewed. Defaulting to the
reviewer-nudge variant without that inspection is noisy — it
burns a maintainer's attention on a PR whose owner hasn't
actually done the work yet.

### Default — author-primary nudge *(use unless the inspection below says otherwise)*

```markdown
@<author> — This PR has new commits since the last review requesting changes from <reviewer_logins>. Could you address the outstanding review comments and either push a fix or reply in each thread explaining why the feedback doesn't apply? When you believe the threads are resolved, please mark them as resolved and ping the reviewer (<reviewer_logins>) — they'll either re-review or hand the PR back to the queue. Thanks!

<ai_attribution_footer>
```

### Reviewer-re-review nudge — only when the inspection shows the feedback has been addressed

```markdown
@<author> <reviewers> — This PR has new commits since the last review requesting changes, and the diff looks like it addresses the feedback (see <thread-links>). @<reviewers>, could you take another look when you have a chance to confirm? Thanks!

<ai_attribution_footer>
```

### How to decide which variant to use

Before drafting, fetch the post-review diff and the conversation
on each thread:

1. `gh api repos/<upstream>/pulls/<N>/reviews/<review_id>/comments --jq '.'`
   to see the reviewer's line-level comments.
2. `gh pr diff <N> --repo <upstream>` limited to the files
   the reviewer commented on.
3. Author replies in-thread (`reviewThreads.nodes.comments.nodes`
   from the batch query) where the author responded after the
   review.

Flip to the reviewer-re-review variant **only when all** of the
following are true:

- Every inline comment the reviewer left has either a code
  change in the post-review diff at or near the commented line,
  **or** an author reply in-thread explaining the
  intentional deviation.
- The thread-level replies read as "done" / "fixed" / "pushed a
  commit", not as "can you clarify" / "I disagree".
- At least one commit was pushed after the review's
  `submittedAt` timestamp.

Otherwise, stay with the author-primary nudge — the ball is in
the author's court and the reviewer should not be re-summoned.

If multiple reviewers are stale and only some have had their
feedback addressed, **use the default (author-primary) variant**
and list all reviewers in the mention — one less noisy message
is preferable to two split ones, and the author gets one
coherent to-do list.

---

## Reviewer ping

*(`reviewer-ping` — unresolved-review-thread ping)*

Used when the action is `ping` on a `deterministic_flag`
classification triggered by unresolved review threads (i.e.
the reviewer commented but the thread stayed unresolved and the
author may have responded).

**Strongly prefer pinging the author** to resolve the
outstanding threads. The skill may only flip to pinging the
reviewer when the same inspection protocol from
[`#review-nudge`](#review-nudge) above has confirmed that the
feedback was addressed and the threads just need a re-look to
be resolved.

### Default — author-primary nudge *(use unless the inspection below says otherwise)*

```markdown
@<author> — There are <N> unresolved review thread(s) on this PR from <reviewer_logins>. Could you either push a fix or reply in each thread explaining why the feedback doesn't apply? When you believe the feedback is addressed, please mark the threads as resolved and ping the reviewer (<reviewer_logins>) for a final look. Thanks!

<ai_attribution_footer>
```

### Reviewer-re-review nudge — only when the inspection shows the feedback has been addressed

```markdown
<reviewers> — @<author> appears to have addressed your review feedback (see the linked threads and the commits pushed since). Could you confirm and resolve the threads if you agree? Thanks!

@<author>, if any of the threads still need work on your side, please reply in-line and push a fix.

<ai_attribution_footer>
```

The decision rule is the same as `review-nudge`: go with the
author-primary nudge by default; only use the reviewer-re-review
variant after an explicit inspection confirms the comments have
been addressed in a post-review commit or resolved with an
in-thread reply.

---

## Request author confirmation

*(`request-author-confirmation` — ask-author-if-ready comment)*

Used when the action is `request-author-confirmation` (see
[`actions.md#request-author-confirmation`](actions.md)). The
PR's only outstanding signal is unresolved review threads, the
[`unresolved_threads_only_likely_addressed`](classify-and-act.md#unresolved_threads_only_likely_addressed)
heuristic fired (engagement signal — not resolution signal),
and we are asking the author to confirm before the PR is
promoted into the maintainer review queue.

The body **must** include the literal marker string
`ready for maintainer review confirmation` verbatim. The
[`viewer_confirmation_request_present`](classify-and-act.md#viewer_confirmation_request_present)
precondition searches for that exact text on subsequent sweeps;
paraphrasing it breaks the gated flow.

```markdown
@<author> — There are <N> unresolved review thread(s) on this PR from <reviewer_logins>, and you have engaged with each one (post-review commits and/or in-thread replies). Could you confirm whether you believe the feedback is fully addressed and the PR is ready for maintainer review confirmation?

If yes, please mark the thread(s) as resolved and ping the reviewer (<reviewer_logins>) for a final look. They will either label the PR ready for maintainer review or follow up with additional feedback.

If you are still working on a thread, please reply with what is outstanding so the threads stay unresolved on purpose.

<ai_attribution_footer>
```

Notes on the body:

- **`@<author>` is mentioned once at the top.** They are the
  only person whose input we need *right now*.
- **`<reviewer_logins>` (not `<reviewers>`) for the reviewer
  reference.** Backtick-quoted, no `@`-ping. The reviewer is
  mentioned for context — telling the author who left the
  feedback — but pinging them in our message would build a
  notification on the engagement signal alone, which is the
  failure mode this two-sweep flow exists to avoid. The author
  pings the reviewer themselves when they're ready, completing
  the hand-back. See [Reviewer-mention policy](#reviewer-mention-policy).
- **The marker string `ready for maintainer review
  confirmation`** appears verbatim in the first paragraph.
  Do not edit the wording around it in a way that breaks the
  substring match (case-sensitive).
- **No "no rush" line.** The author is the only one who can
  move the PR forward at this step; framing the ask softly
  matters more than a decompression line.
- **The `<ai_attribution_footer>` applies** — this is a
  contributor-facing comment drafted by the bot, and the
  author should know that.

If the author replies affirmatively, the next sweep classifies
the PR as
[`author_confirmation_received`](classify-and-act.md#author_confirmation_received)
and the triaging maintainer is offered the
[`mark-ready`](actions.md#mark-ready--add-ready-for-maintainer-review-label)
action with the author's reply visible alongside the proposal.
If the author replies with "still working on X" or a clarifying
question, the maintainer overrides the proposal to `skip` or
`[O]ping` from the group menu.

If the author is silent past the cooldown, the
[stale author-confirm-request sweep](stale-sweeps.md#sweep-5--stale-author-confirm-request)
takes over.

---

## Stale draft close

*(`stale-draft-close` — stale draft closing comment)*

Used by the stale-sweep flow when a draft PR's triage comment
is older than 7 days with no author reply (see
[`stale-sweeps.md#stale-draft`](stale-sweeps.md)).

```markdown
@<author> This draft PR has been inactive for <days_since_triage> days since the last triage comment and no response from the author. Closing to keep the queue clean.

You are welcome to reopen this PR when you resume work, or to open a new one addressing the issues previously raised. There is no rush — take your time.

<ai_attribution_footer>
```

### Untriaged-draft variant

Used for drafts that were never triaged but have gone 3+ weeks
with no activity:

```markdown
@<author> This draft PR has had no activity for <weeks_since_activity> weeks. Closing to keep the queue clean.

You are welcome to reopen and continue when you're ready. If you'd like to pick it back up, please rebase onto the current `<base>` branch first.

<ai_attribution_footer>
```

---

## Inactive to draft

*(`inactive-to-draft` — convert inactive non-draft to draft)*

Used by the stale-sweep flow when an open (non-draft) PR has
had no activity for 4+ weeks.

```markdown
@<author> This PR has had no activity for <weeks_since_activity> weeks. Converting to draft to signal that maintainer review is paused until you resume work.

When you're ready to continue, please rebase onto the current `<base>` branch, address any newly-appearing CI failures, and mark the PR as "Ready for review" again. There is no rush.

<ai_attribution_footer>
```

No label is added — the conversion itself is the signal.

---

## Stale ready-label close

*(`stale-ready-label-close` — close a label-flagged PR after author silence + bitrot)*

Used by [Sweep 4b](stale-sweeps.md#4b--branch-rotted--propose-close).

```markdown
@<author> This PR has had no author response for <days_since_maintainer> days since the last maintainer comment, and the branch now has <bitrot_signal>. Closing to keep the queue clean.

When you're ready to resume, please rebase onto the current `<base>` branch, address any failing checks, and either reopen this PR or open a fresh one. There is no rush.

<ai_attribution_footer>
```

`<bitrot_signal>` ∈ {`failing CI`,
`merge conflicts with <base>`, `failing CI and merge conflicts with <base>`},
keyed off `statusCheckRollup.state == FAILURE` and
`mergeable == CONFLICTING`.

---

## Stale workflow approval

*(`stale-workflow-approval` — convert stale WF-approval to draft)*

Used by the stale-sweep flow when a PR awaiting workflow
approval has had no activity for 4+ weeks.

```markdown
@<author> This PR has been awaiting workflow approval with no activity for <weeks_since_activity> weeks. Converting to draft so it doesn't block the first-time-contributor review queue.

When you're ready to continue, please push a new commit (which will re-request workflow approval) and mark the PR as "Ready for review" again. There is no rush.

<ai_attribution_footer>
```

---

## Suspicious changes

*(`suspicious-changes` — flag-as-suspicious comment)*

Used by the `flag-suspicious` action when a first-time-
contributor workflow-approval PR shows tampering indicators
(see [`workflow-approval.md#what-counts-as-suspicious`](workflow-approval.md)).

Posted on every currently-open PR by the flagged author as
part of the per-author sweep — keep it short and non-accusatory.

```markdown
This PR has been closed because of suspicious changes detected in it or in another PR by the same author. If you believe this is in error, please contact the <PROJECT> maintainers on the [<project_communication_channel>](<project_communication_url>).
```

Do **not** enumerate which patterns triggered the flag in the
comment — that's operational detail that belongs in the
maintainer-side session summary, not in a message to the
contributor.

Do **not** append the `<ai_attribution_footer>` here. This
template is intentionally terse and already directs the
contributor to maintainers on Slack if the flag was in error —
adding the "an AI may have gotten this wrong" footer on a
suspicious-changes close would dilute the signal and give a
bad-faith actor a footnote to argue with.

---

## Violations rendering

`<violations>` in the templates above expands to a bullet list,
one bullet per violation returned by the classifier. Each
bullet has the form:

```markdown
- :x: **<category>** — <explanation>. See [docs](<doc_link>).
```

- `:x:` for severity `error`, `:warning:` for severity `warning`.
- `<category>` — short category name, e.g.
  `Merge conflicts`, `mypy (type checking)`,
  `Unresolved review comments`.
- `<explanation>` — one short clause stating what's wrong
  (e.g. *"Failing: mypy-core, mypy-providers"*).
- `<doc_link>` — link to the canonical doc that explains how to
  fix this category. Do **not** inline project-specific
  commands or step-by-step remediation prose in the bullet —
  the linked doc has them. Keep the bullet to one line.

The category / explanation / doc-link triples come from
`assess_pr_checks` / `assess_pr_conflicts` /
`assess_pr_unresolved_comments`-equivalent logic — this skill
reproduces those deterministic assessments without the LLM
layer.  The canonical categories and their doc links are read
from `<project-config>/pr-management-triage-ci-check-map.md` at
session start.  The skill matches failed check names against
the patterns in that file (first-match-wins) and uses the
corresponding category name + doc URL for the violation bullet.

The table below shows the **shape** of the mapping; concrete
values live in the adopter config:

| Category | Signal | Doc link source |
|---|---|---|
| `Merge conflicts` | `mergeable == CONFLICTING` | `<project-config>/pr-management-triage-ci-check-map.md` → merge-conflicts row |
| `Failing CI checks` (fallback) | `checks_state == FAILURE`, no failed names available | `<project-config>/pr-management-triage-ci-check-map.md` → catch-all row |
| `Pre-commit / static checks` | failed check name matches `static checks`, `pre-commit`, `prek` | `<project-config>/pr-management-triage-ci-check-map.md` → corresponding row |
| `Ruff (linting / formatting)` | `ruff` | `<project-config>/pr-management-triage-ci-check-map.md` → corresponding row |
| `mypy (type checking)` | `mypy-*` | `<project-config>/pr-management-triage-ci-check-map.md` → corresponding row |
| `Unit tests` | `unit test`, `test-` | `<project-config>/pr-management-triage-ci-check-map.md` → corresponding row |
| `Build docs` | `docs`, `spellcheck-docs`, `build-docs` | `<project-config>/pr-management-triage-ci-check-map.md` → corresponding row |
| `Helm tests` | `helm` | `<project-config>/pr-management-triage-ci-check-map.md` → corresponding row |
| `Kubernetes tests` | `k8s`, `kubernetes` | `<project-config>/pr-management-triage-ci-check-map.md` → corresponding row |
| `Image build` | `build ci image`, `build prod image`, `ci-image`, `prod-image` | `<project-config>/pr-management-triage-ci-check-map.md` → corresponding row |
| `Provider tests` | `provider` | `<project-config>/pr-management-triage-ci-check-map.md` → corresponding row |
| `Other failing CI checks` | anything uncategorised | `<project-config>/pr-management-triage-ci-check-map.md` → catch-all row |
| `Unaddressed Copilot review` | classification `stale_copilot_review` — unresolved review thread by a `copilot*[bot]` login older than 7 days with no author reply | `<project-config>/pr-management-triage-comment-templates.md` → `<quality_criteria_url>` |
| `Unresolved review comments` | `unresolved_threads > 0` | `<project-config>/pr-management-triage-comment-templates.md` → `<quality_criteria_url>` |

When a category has multiple matching failed check names,
list the first 5 and summarise the rest as `(+N more)`.

---

## Tone rules

- **No emoji in the body text.** The severity icons `:x:` and
  `:warning:` are the only "emoji" allowed, and only because
  GitHub renders them inline and they're informative.
- **No scare-quoted words.** Don't write *"This PR has 'issues'"*.
- **Always include the no-rush line** in `draft`, `comment-only`,
  and `close` — contributors who see triage output feel
  time-pressure by default; the explicit de-pressurisation is
  part of the contract.
- **Always include the `<ai_attribution_footer>`** on every
  contributor-facing template (the only exception is
  `suspicious-changes`; see the note there). The footer
  calibrates trust in the AI-drafted message and links to the
  project's documented two-stage-triage rationale.
- **Mentions: `@<author>` gets one mention per comment, at the
  top.** Further mentions beyond the first are noise — they
  all hit the same notification anyway.
- **Sign-off: none.** Don't add "Thanks," or the maintainer's
  name. The comment comes from the triage tool and reads as
  such; signing it adds noise and invites replies directed at
  the wrong human.
