<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill's frontmatter `name:` is `magpie-pr-management-code-review`.

cat skills/code-review/SKILL.md (frontmatter, this skill's own file):
  name: magpie-pr-management-code-review
  surface_hash: sha256:9f1c4e2a7b3d5c11

cat .apache-magpie.lock:
  method: marketplace
  url: apache/magpie
  floor:
    magpie-pr-management: 0.9.0
  reconciled:
    version: 0.2.0.dev202609211315
    at:      2026-09-21
    skills:
      magpie-pr-management-code-review: sha256:9f1c4e2a7b3d5c11
      magpie-security-issue-triage:     sha256:4ab70d1e88221fa0
