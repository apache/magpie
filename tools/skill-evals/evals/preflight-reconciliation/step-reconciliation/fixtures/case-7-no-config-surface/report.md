<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill's frontmatter `name:` is `magpie-list-skills`.

cat skills/list-skills/SKILL.md (frontmatter, this skill's own file):
  name: magpie-list-skills
  surface_hash: sha256:7c31ae09b5d4e620
  (no `requires_config:` key at all — this skill reads no project
  configuration, and no override file names it)

cat .apache-magpie.lock:
  method: marketplace
  url: apache/magpie
  floor:
    magpie-utilities: 0.1.0
  reconciled:
    version: 0.2.0.dev202609180100
    at:      2026-09-18
    skills:
      magpie-pr-management-code-review: sha256:9f1c4e2a7b3d5c11
      magpie-security-issue-triage:     sha256:4ab70d1e88221fa0

cat .apache-magpie-local/reconciled.json:
  {
    "verified_at": "2026-09-18"
  }

ls .apache-magpie-overrides/:
  project.md
  reviewer-roster.md

claude plugin list --json (readable in this session):
  [{"name": "magpie-utilities", "version": "0.2.0.dev202609180100"}]
  (satisfies the 0.1.0 floor, so step 3 of the pre-flight passes
  silently and does not skip step 4)
