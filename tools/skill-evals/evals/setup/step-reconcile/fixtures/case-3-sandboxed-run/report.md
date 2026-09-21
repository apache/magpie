<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `marketplace`.

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

Attempt to read the target skill's `SKILL.md`:
  ~/.claude/plugins/cache/apache-magpie/magpie-pr-management/0.9.3/skills/code-review/SKILL.md
  -> read denied (sandbox filesystem policy excludes the plugin cache)
