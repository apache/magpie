<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Golden rule 9 — out of scope: triage actions.** This skill
does not convert PRs to draft, close them, rebase them, ping
reviewers, or rerun CI. Those are
[`pr-management-triage`](../pr-triage/SKILL.md) actions. If the maintainer
discovers during review that a PR needs a triage action (e.g. it
should really be drafted because of merge conflicts that
appeared), the skill says so explicitly and points them at
`pr-management-triage pr:<N>`. It does not silently invoke triage actions.

**Exception — slop-detection early exit** — full carve-out text in [`slop-detection.md`](slop-detection.md).

## What this skill deliberately does NOT do

- **First-pass triage actions.** Drafting, rebasing,
  pinging, rerunning CI, marking `ready for maintainer review` —
  all live in [`pr-management-triage`](../pr-triage/SKILL.md). If the
  current PR needs one of those, the skill says so and points
  at `pr-management-triage pr:<N>`. *(Exception: the
  slop-detection `[X]` close+lock path — see Golden rule 9.)*
- **Requesting or notifying reviewers.** Step 4.5 *names*
  domain experts in the review body as backtick-quoted handles;
  it never live-`@`-mentions them (see the mention policy in
  [`posting.md#mention-policy`](posting.md)), never calls
  `gh pr edit --add-reviewer`, and never uses the
  `requestReviews` mutation. Formally requesting a reviewer is
  a separate maintainer action (or a job for
  [`reviewer-routing`](../reviewer-routing/SKILL.md)).
- **Merging.** Merging is a conscious maintainer action that
  belongs in a separate flow.
- **Submitting reviews on closed / merged PRs.** The skill only
  reviews open PRs.
- **Running CI locally.** The skill examines the diff and
  reasons about it; running tests locally before approving is a
  judgment call the maintainer makes per PR (the `dry-run`
  selector and `[S]kip-for-now` exit are how that gets handled
  inside this skill).
- **Modifying PR code.** This skill never pushes commits, never
  proposes patches via `gh pr review --suggested-changes`
  beyond the verbatim suggestion blocks in
  [`posting.md`](posting.md), and never edits the contributor's
  branch.
- **Bypassing the project's review criteria.** Findings cite
  specific rules from the source files declared in
  `<project-config>/pr-management-code-review-criteria.md` and
  from the project's repo-wide [`AGENTS.md`](../../../../AGENTS.md).
  New review philosophies belong in those files first; this
  skill picks them up automatically once they land.
