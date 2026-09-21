<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill's frontmatter `name:` is `magpie-pr-management-code-review`.

cat skills/code-review/SKILL.md (frontmatter, this skill's own file):
  name: magpie-pr-management-code-review
  requires_config:
    - fix-workflow.md
    - reviewer-routing.md
  surface_hash: sha256:7c2a91ff408b6e33

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

cat .apache-magpie-local/reconciled.json:
  (file does not exist)

Lookup-chain resolution for this skill's requires_config right now:
  .apache-magpie-local/fix-workflow.md            -> present
  .apache-magpie-overrides/fix-workflow.md        -> present
  .apache-magpie-local/reviewer-routing.md        -> absent
  .apache-magpie-overrides/reviewer-routing.md    -> absent
