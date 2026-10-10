<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Posting reviews

How the findings list becomes a GitHub review submission.
`pr-management code-review render` builds everything posted — the body, the inline threads, the footer — and prints the exact post command; this file is the policy it implements and the checks around the post.

---

## Mention policy

> **This section is normative and applies to every character this
> skill posts** — the review body, every inline review comment,
> findings folded in from an adversarial reviewer, and any
> contributor text quoted inside a finding. It is the review-side
> counterpart of the author-only notification rule in
> [`pr-management-triage`](../../../../tools/pr-management/README.md#triage-render--the-contributor-facing-bodies).

Submitting a review already notifies the PR author and every
subscriber — that is all the notification a review needs. A live
`@`-mention additionally summons the named person, without their
consent, onto a thread where nothing is being asked of them.

- **Nothing this skill posts ever live-`@`-mentions anyone** —
  not suggested reviewers, not `CODEOWNERS` owners or teams, not
  the PR author, not the operator. When a handle must appear
  (a suggested reviewer, the author of a prior review being
  referenced), render it **backtick-quoted** — `` `@login` `` /
  `` `@org/team` `` — which reads as a handle without producing
  a notification.
- **Quoted contributor text is escaped too.** Commit messages,
  PR-body excerpts, and code comments quoted into a finding may
  carry `@handle` tokens; keep such quotes inside code spans or
  fenced blocks so GitHub never processes the mentions.
- **Adversarial fold-in is covered.** Findings imported from a
  second reviewer (Step 5 of [`review-flow.md`](review-flow.md))
  get the same escaping before composition — the other tool's
  output is not exempt.
- **A deliberate ping is still possible — never silent.** The
  mention scan in Step 8 of
  [`review-flow.md`](review-flow.md) flags any live mention that
  survives drafting and posts it only on the maintainer's
  explicit `[K]eep`. Formally requesting a reviewer remains a
  separate action
  ([`reviewer-routing`](../reviewer-routing/SKILL.md)).

---

## Disposition

`pr-management code-review disposition` picks it; the maintainer may override with `[A]` / `[R]` / `[C]`.

| Disposition | When |
|---|---|
| `APPROVE` | every gate holds: rollup `SUCCESS` and real CI ran (Golden rule 8); no unresolved review thread, no other maintainer's standing `CHANGES_REQUESTED`, no unanswered maintainer question (Golden rule 7); no finding above `nit` |
| `REQUEST_CHANGES` | ≥ 1 `blocking`, OR ≥ 2 `major`, OR `major` + unanswered author question, OR a CI failure judged diff-caused, OR a finding the maintainer wants to gate the merge on |
| `COMMENT` | everything else: findings above `nit` without a gating count, CI pending or failing outside the diff, threads open, observations without gating |

### Conflicts are always stated in the body

A PR whose `mergeStateStatus` is `DIRTY` (or whose `mergeable` is
`CONFLICTING`) **must say so in the review body**, whatever the
disposition. One sentence naming the state and asking for a rebase
onto the base branch is enough:

> The branch currently conflicts with `main` and needs a rebase
> before this can merge.

Conflicts do **not** by themselves force `REQUEST_CHANGES`. A PR can
be entirely correct and still trail its base, and gating an otherwise
finished review behind a mechanical rebase wastes a round trip. But
saying nothing is worse: the author sees an approving review, assumes
the PR is done, and only discovers the conflict when a maintainer
reaches the merge button — by which point the reviewer has moved on.
Approving a branch that cannot merge, without mentioning it, is the
failure this rule exists to prevent.

Where the conflict state is `UNKNOWN` after a re-read (see
[`review-flow.md` § Step 2](review-flow.md)), say that instead of
claiming the branch is clean.

Rebasing the branch is a triage action, not a review action — point
the maintainer at `pr-management-triage pr:<N>` rather than
doing it here (Golden rule 9, in [`scope.md`](scope.md)).

---

## The post

`render` prints `post_command`:

- with inline threads: `gh api graphql --input <payload>` — one `addPullRequestReview` mutation carrying the body and every kept thread, each placed by `path` + `line` + `side` (RIGHT for an added or context line, LEFT for a removed one) computed from the saved diff;
- body-only (no inline thread survived, or `inline:off`): `gh pr review <N> --repo <repo> --approve|--request-changes|--comment --body-file <file>`.

Both read the body from a file, never an inline string. Run the command exactly as printed, as a bare command, only after the maintainer confirmed the body.

### Confirm the review posted — never re-run on empty output

`gh pr review` **prints nothing on success.** Empty output is the
expected result, not a failure, and re-running the command because it
"looked like nothing happened" submits the review a second time.

That second review cannot be taken back. GitHub's API deletes only
*pending* reviews: `DELETE /repos/{owner}/{repo}/pulls/{n}/reviews/{id}`
answers `422 Can not delete a non-pending pull request review` for
anything already submitted. The best available repair is to `PUT` the
duplicate's body down to a one-line pointer at the real one, which
leaves a visibly confused thread on a contributor's PR.

So verify the post-condition instead of retrying. After the call, read
the reviews back and confirm exactly one new review from the posting
account:

```bash
gh api repos/<repo>/pulls/<N>/reviews
```

(`render` prints it as `verify_command`; run it as a bare command — a `--jq` filter is fine, a pipe is not — and count the entries whose `user.login` is the viewer.)

Treat a non-zero exit from `gh pr review` as the only failure signal. If
the command exits zero, the review is posted — whatever it printed. If
the exit status is genuinely non-zero, re-check with the query above
before any retry, because a partial failure (for example the review
landing but an inline comment being rejected) can still leave a review
behind.

The same applies to `gh pr comment` and to the `addPullRequestReview`
mutation below.

Inline positions are valid only against the head that was diffed; when the Step 8 `guard` reports new commits, re-run Steps 1–7 (`[R]efresh`) or post body-only (`[B]ody-only-now`).

---

## Review body — template structure

`render` assembles up to five sections, in this order, omitting empty ones:

1. the summary line (yours) — after the security warning, when Step 3 raised one, and with the conflict sentence right after it;
2. blocking findings — `### Blocking — <rule> (<file:line>)`, the verbatim quoted rule, the excerpt, your explanation, an optional `suggestion` block;
3. major findings — the same shape without the prefix;
4. *Smaller observations* — `minor` and `nit` as bullets, with a pointer to the ones kept inline;
5. *Worth a second look from* — the grounded reviewer suggestions, backtick-quoted, with a note that nobody was notified;

then the AI-attribution footer.

### The summary line

One sentence that names the disposition's reason. Examples:

- `APPROVE`: *"LGTM — clean N+1 fix with regression test, CI
  green."*
- `REQUEST_CHANGES`: *"Found 1 blocking issue (potential SQL
  injection in `where` clause) that needs to land before this
  can merge."*
- `COMMENT`: *"Approach looks reasonable; a few observations
  inline that I'd like resolved before merging — none
  blocking."*

The summary line is **never** boilerplate. It's the one piece
of the review body the contributor reads first; it has to
say something specific.

### AI-attribution footer

Every body ends with one of four verbatim blocks (Golden rule 5), shipped as templates in [`tools/pr-management`](../../../../tools/pr-management/src/pr_management/code_review/templates/): `approve`, `request-changes`, `comment-maintainer`, `comment-role-neutral`.
`APPROVE` and `REQUEST_CHANGES` always carry the maintainer-confirmed wording — GitHub refuses them without write access. `COMMENT` has no such gate, so it uses the maintainer-confirmed variant only when the permission read returned `admin`, `maintain` or `write`, and the role-neutral one otherwise (including a `COMMENT` posted after the dry-run warning).
Only `<PROJECT>` and the contributing-docs URL are substituted; with no URL configured, the last two lines are dropped rather than linking to a guess. `render` verifies the footer before it offers the post command; never paraphrase it, never let an edit drop it.

---

## Adversarial-reviewer attribution

When a finding came from an adversarial reviewer, mark it
inline. Name the reviewer when the tool path ran several (*"Flagged by
codex and copilot (adversarial review); cross-checked."*); otherwise:

```markdown
### Blocking — Race condition on lock release (`scheduler.py:312`)

[…]

*Flagged by the adversarial reviewer; cross-checked.*
```

When two reviewers landed on the same finding:

```markdown
*Flagged by both the primary and adversarial reviewers.*
```

This makes the contributor's mental model accurate — they're
not arguing with one tool; they're arguing with two
independently-trained reviewers and a human maintainer who
agreed.

---

## Confirm-before-post

The maintainer's harness-level instructions (`AGENTS.md`,
`~/.claude/CLAUDE.md`) typically include a "confirm before
sending" rule for any message authored on their behalf. The
post step is **always** preceded by:

> *Drafted review (disposition: `<DISP>`):*
>
> ```markdown
> [full body here]
> ```
>
> *Post as-is, or want any edits?*

Wait for explicit confirmation (`yes`, `post`, `go ahead`, or
similar). If the maintainer replies with edits, **re-render
the new body and re-confirm** — earlier `yes` only covers the
exact text it approved.

---

## Per-tone overrides

If the maintainer's harness-level instructions (`AGENTS.md`,
`~/.claude/CLAUDE.md`) define **per-contributor tone overrides**
— e.g. one contributor expects a sharper register, another
gets a more measured tone — the **summary line** and body
wording for the affected PR shift accordingly. The findings
themselves don't change; the framing does.

If a tone override applies, surface it before the maintainer
confirms the body:

> *Tone override active for `<author>` per harness instructions
> (`<override-summary>`). Drafted body reflects that — please
> double-check.*

---

## `dry-run` mode

When the `dry-run` selector is in effect (see
[`invocation.md`](invocation.md)), the post step is replaced with:

> *Dry-run mode: would post `<DISP>` review to PR #N. Move on?
> `[Y]es` (default), `[E]dit`, `[S]kip`, `[Q]uit`.*

`gh pr review` is **not invoked**. The session summary lists
the would-have-been dispositions and counts.
