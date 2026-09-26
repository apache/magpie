<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Discount settings: all defaults (no keys set in committer-readiness.md or contributor-nomination-config.md).
automated_contribution_expectations: none configured.

Authored PRs:
- pr-101 — MERGED. Maintainer @alice (authorAssociation MEMBER) commented: "This reads like unreviewed LLM output. Please review your own changes before pushing." The candidate then pushed fixes and it was merged.
- pr-102 — CLOSED, not merged. Maintainer @bob (authorAssociation MEMBER) commented: "Please stop opening AI-generated PRs that call functions which do not exist." Closed by @bob the same day.
- pr-103 — MERGED. PR description ends with the trailer "Generated-by: Claude Code". No maintainer remarks about generation; approved by @alice with "Nice, thanks."

Comment threads (candidate's comments on others' PRs):
- thread-200 — the candidate's only comment is a bullet list repeating the PR description's summary of the three changed files, with no question, finding, or suggestion.
- thread-201 — the candidate asked: "Does this also handle the retry path in the scheduler loop? I could not see a test for it."
