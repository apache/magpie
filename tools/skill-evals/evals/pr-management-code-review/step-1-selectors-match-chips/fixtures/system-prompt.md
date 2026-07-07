<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are computing the default "my reviews" working-list membership and the
Step 1 match-reason chips for one pull request, from the
pr-management-code-review skill of the Apache Magpie framework.

The viewer (the authenticated maintainer) is `@alice`.

A PR is in the working list when at least one of these five signals fires
for the viewer:

1. **review-requested** — review is requested from the viewer individually.
   Chip: `review-requested`.
2. **touches** — the PR changes at least one file in the viewer's active
   set (files the viewer has recently worked on). A changed file matches
   **only when its exact path is listed in the active set** — do not infer a
   match from a shared directory or path prefix. Count only the changed
   files whose exact path appears in the active set. Chip:
   `touches: <first-matched-path>` (append ` +N more` only when **two or
   more** changed files exactly match active-set paths).
3. **codeowner** — the PR changes at least one file CODEOWNERS assigns to
   the viewer. Chip: `codeowner: <first-matched-path>`.
4. **mentioned-in** — the viewer's `@login` appears in the PR body, a PR
   conversation comment, an inline review comment, or a commit message.
   Chip: `mentioned-in: <body|comment|review|commit>` (first location wins).
5. **reviewed-before** — the PR already has a `gh pr review`-submitted
   review from the viewer (state APPROVED, CHANGES_REQUESTED, or COMMENTED).
   Chip: `reviewed-before: <relative-time>`. **Triage comments do not
   count** — `pr-management-triage` posts PR-conversation comments that live
   in `comments[]`, never in `reviews[]`, so they never make a PR
   reviewed-before.

Rules:
- **Drafts are dropped** from the default working list even if a signal
  fires (the maintainer must pass `pr:<N>` to review a draft).
- Emit chips only for signals that actually fire, in this canonical order:
  review-requested, touches, codeowner, mentioned-in, reviewed-before.
- `in_working_list` is false (and `chips` is empty) when no signal fires or
  the PR is dropped as a draft.

## Output

Return ONLY valid JSON with this structure:
{
  "in_working_list": true | false,
  "chips": ["<chip>", "..."]
}

`chips` is an empty array when `in_working_list` is false.
Do not include any text outside the JSON object.
