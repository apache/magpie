<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `git-branch` (pinned snapshot).

Scope: 1 configured skill, 1 override file.

Configured skill: `magpie-pr-management-code-review`
  `requires_config:`
    - fix-workflow.md
    - reviewer-routing.md
  Lookup-chain resolution:
    .apache-magpie-local/fix-workflow.md          -> absent
    .apache-magpie-overrides/fix-workflow.md      -> present
    .apache-magpie-local/reviewer-routing.md      -> absent
    .apache-magpie-overrides/reviewer-routing.md  -> present

Override file: `.apache-magpie-overrides/pr-management-code-review.md`
  Anchor referenced in the override: "Step 4 — Post the review"

  `.apache-magpie/skills/code-review/SKILL.md` is readable (pinned
  snapshot — no plugin cache involved). Current headings:
    ## Step 3 — Draft the findings
    ## Step 4 — Post the review
    ## Step 5 — Recap
