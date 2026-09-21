<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `git-branch` (pinned snapshot). `.apache-magpie.lock`
exists in this repo (adopted).

Two override files in `.apache-magpie-overrides/`:

Override 1: `.apache-magpie-overrides/pr-management-code-review.md`
  Target skill: `magpie-pr-management-code-review` — exists in the new
    snapshot.
  Anchor referenced: "Step 4 — Post the review".
    `.apache-magpie/skills/code-review/SKILL.md` current headings:
      ## Step 3 — Draft the findings
      ## Step 4 — Post the review
      ## Step 5 — Recap
    (unchanged — the anchor resolves.)
  `requires_config:` for this skill: fix-workflow.md, reviewer-routing.md
    .apache-magpie-local/fix-workflow.md          -> absent
    .apache-magpie-overrides/fix-workflow.md      -> present
    .apache-magpie-local/reviewer-routing.md      -> absent
    .apache-magpie-overrides/reviewer-routing.md  -> present
    (both resolve.)
  Current `surface_hash` (from its `SKILL.md` frontmatter, already in
    context): sha256:1d0038ec4fde60bf

Override 2: `.apache-magpie-overrides/issue-triage.md`
  Target skill: `magpie-security-issue-triage` — exists in the new
    snapshot.
  Anchor referenced: "Step 3 — Read the report and classify".
    `.apache-magpie/skills/issue-triage/SKILL.md` current headings
    include that exact heading, unchanged — the anchor resolves.
  `requires_config:` for this skill: project.md, scope-labels.md,
    security-model.md
    .apache-magpie-local/project.md              -> present
    .apache-magpie-overrides/project.md          -> (n/a, found locally)
    .apache-magpie-local/scope-labels.md         -> absent
    .apache-magpie-overrides/scope-labels.md     -> absent
    .apache-magpie-local/security-model.md       -> present
    .apache-magpie-overrides/security-model.md   -> (n/a, found locally)
    (`scope-labels.md` resolves through neither.)
  Current `surface_hash` (from its `SKILL.md` frontmatter, already in
    context): sha256:f4050980e99e977e

Today: 2026-09-21
