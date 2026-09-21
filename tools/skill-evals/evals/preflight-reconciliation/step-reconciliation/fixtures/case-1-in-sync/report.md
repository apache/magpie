<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill is `magpie-pr-management/code-review`.

cat skills/code-review/SKILL.md (frontmatter, this skill's own file):
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
      magpie-pr-management/code-review: sha256:9f1c4e2a7b3d5c11
      magpie-security/issue-triage:     sha256:4ab70d1e88221fa0

cat .apache-magpie-local/reconciled.json:
  {}

claude plugin list --json (readable in this session):
  [{"name": "magpie-pr-management", "version": "0.2.0.dev202609211315"}]

~/.claude/plugins/marketplaces/apache-magpie (readable in this session):
  latest tag for magpie-pr-management: 0.2.0.dev202609211400
  (one dev build ahead of the installed 0.2.0.dev202609211315)

Result: the stamped hash for `magpie-pr-management/code-review`
(sha256:9f1c4e2a7b3d5c11) matches the skill's own current
`surface_hash` (sha256:9f1c4e2a7b3d5c11) exactly.
