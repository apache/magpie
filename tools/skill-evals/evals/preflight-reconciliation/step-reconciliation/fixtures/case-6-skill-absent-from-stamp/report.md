<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill's frontmatter `name:` is `magpie-reviewer-routing`.

cat skills/reviewer-routing/SKILL.md (frontmatter, this skill's own file):
  name: magpie-reviewer-routing
  requires_config:
    - project.md
    - reviewer-roster.md
  surface_hash: sha256:b90a1c44de77f102

cat .apache-magpie.lock:
  method: marketplace
  url: apache/magpie
  floor:
    magpie-pr-management: 0.9.0
  reconciled:
    version: 0.2.0.dev202609180100
    at:      2026-09-18
    skills:
      magpie-pr-management-code-review: sha256:9f1c4e2a7b3d5c11
      magpie-security-issue-triage:     sha256:4ab70d1e88221fa0
  (magpie-reviewer-routing was configured after this stamp was written
  and has never been reconciled — it does not appear in `skills:`
  above)

cat .apache-magpie-local/reconciled.json:
  {
    "verified_at": "2026-09-18"
  }
  (no `skills` entry for magpie-reviewer-routing here either, and no
  `acknowledged` block at all yet)

claude plugin list --json (readable in this session):
  [{"name": "magpie-pr-management", "version": "0.2.0.dev202609180100"}]
