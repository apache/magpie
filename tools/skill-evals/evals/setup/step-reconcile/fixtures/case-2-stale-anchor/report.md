<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `git-branch` (pinned snapshot).

Scope: 1 configured skill, 1 override file.

Configured skill: `magpie-security-issue-triage`
  `requires_config:`
    - project.md
    - canned-responses.md
  Lookup-chain resolution:
    .apache-magpie-local/project.md                -> present
    .apache-magpie-overrides/project.md            -> present
    .apache-magpie-local/canned-responses.md       -> absent
    .apache-magpie-overrides/canned-responses.md   -> present

Override file: `.apache-magpie-overrides/security-issue-triage.md`
  Anchor referenced in the override: "Step 3 — Classify the disposition"

  `.apache-magpie/skills/issue-triage/SKILL.md` is readable (pinned
  snapshot — no plugin cache involved). Current headings:
    ## Step 2 — Read the report and comments
    ## Step 3 — Read the report and classify
    ## Step 4 — Post the triage-proposal comment
