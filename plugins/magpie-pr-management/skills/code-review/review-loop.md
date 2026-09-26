<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Step 2 — Sequential per-PR review

For each PR in the list, run the per-PR review loop in
[`review-flow.md`](review-flow.md). The loop is:

1. **Present headline** — PR number, title, author, label chips,
   CI state, threads count, ±LOC summary, files changed count.
2. **Fetch diff and PR body** — via `gh pr diff <N>` and `gh pr
   view <N> --json body,...`.
3. **Examine the diff against the criteria** from
   [`criteria.md`](criteria.md), grouping findings by category:
   architecture, DB/query correctness, code quality, testing,
   API correctness, generated files, AI-generated-code signals,
   and any provider/area-specific rules pulled from the relevant
   `AGENTS.md` (see [`review-flow.md#area-specific`](review-flow.md)).
4. **Optionally run the adversarial reviewer** — if a
   second-reviewer plugin is configured (Step 0), propose
   invoking it now and integrate its findings (see
   [`adversarial.md`](adversarial.md)). The user runs the slash
   command; the skill resumes once the user pastes / continues
   with the output.
5. **Draft the review body and disposition** — pick `APPROVE`,
   `REQUEST_CHANGES`, or `COMMENT` per the rules in
   [`posting.md#disposition`](posting.md), apply Golden rules 7
   and 8, and produce a draft body using the templates in
   [`posting.md`](posting.md). The body may close with up to
   2–3 **suggested additional reviewers** — domain experts for
   the touched area, derived from `CODEOWNERS` and commit /
   review history per
   [`review-flow.md#step-45`](review-flow.md), never fabricated,
   never auto-requested, and named with backtick-quoted handles
   so nobody is notified (see the mention policy in
   [`posting.md#mention-policy`](posting.md)).
6. **Show the inline-comments picker** — inline review
   comments are the **default and preferred** output of this
   skill: for every anchored finding the skill drafts an
   inline review comment and presents them in a numbered list
   with all entries enabled by default, so the maintainer
   accepts them individually. The maintainer picks `[A]ll` /
   `[N]one` / `[<indices>]` / drops a few. A body-only review
   is the explicit exception, reached only by passing
   `inline:off`, which suppresses the picker for the whole
   session. Findings that cannot be anchored to a `file:line`
   (e.g. on unchanged lines) go in the review body instead.
7. **Show the draft to the maintainer** — full body, count of
   inline comments to be posted, and the chosen disposition.
8. **On confirmation** — post via the GraphQL
   `addPullRequestReview` mutation (or `gh pr review` if no
   inline comments survived the picker). See
   [`posting.md`](posting.md). On rejection — capture the
   maintainer's edits and re-draft.
9. **On `[S]kip`** — leave the PR alone and move on.
10. **On `[Q]uit`** — exit the session.
