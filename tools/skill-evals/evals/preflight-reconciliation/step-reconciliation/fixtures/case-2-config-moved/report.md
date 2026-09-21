<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill is `magpie-pr-management/code-review`.

cat skills/code-review/SKILL.md (frontmatter, this skill's own file):
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
      magpie-pr-management/code-review: sha256:9f1c4e2a7b3d5c11
      magpie-security/issue-triage:     sha256:4ab70d1e88221fa0

cat .apache-magpie-local/reconciled.json:
  {}

Lookup-chain resolution for this skill's requires_config right now:
  .apache-magpie-local/fix-workflow.md            -> present
  .apache-magpie-overrides/fix-workflow.md        -> present
  .apache-magpie-local/reviewer-routing.md        -> absent
  .apache-magpie-overrides/reviewer-routing.md    -> absent
  (reviewer-routing.md is new since the stamped hash was written; nothing
  in either layer resolves it yet)

claude plugin list --json (readable in this session):
  [{"name": "magpie-pr-management", "version": "0.2.0.dev202609211315"}]

~/.claude/plugins/marketplaces/apache-magpie (readable in this session):
  latest tag for magpie-pr-management: 0.2.0.dev202609211400
  (one dev build ahead of the installed 0.2.0.dev202609211315)

Result: the stamped hash for `magpie-pr-management/code-review`
(sha256:9f1c4e2a7b3d5c11) differs from the skill's own current
`surface_hash` (sha256:7c2a91ff408b6e33). The new `reviewer-routing.md`
requires_config entry does not resolve through the lookup chain.
