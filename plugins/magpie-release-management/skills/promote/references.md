<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-promote — references

- [`docs/release-management/process.md`](../../../../docs/release-management/process.md) — Step 10 context.
- [`docs/release-management/spec.md`](../../../../docs/release-management/spec.md) — `release-promote` per-skill specification and Boundary 2.
- [`<project-config>/release-management-config.md`](../../../magpie-setup/templates/release-management-config.md) —
  adopter keys this skill reads (`release_dist_backend`, `release_dist_url_template`, `release_publish_command_template`).
- [`<project-config>/pmc-roster.md`](../../../magpie-setup/templates/pmc-roster.md) —
  PMC membership roster (used for the PMC gate; the default `release_approver_roster_path`).
- `release-vote-tally` (proposed) — upstream step; `vote-passed` label is the gate.
- `release-announce-draft` — downstream step; drafts the `[ANNOUNCE]` email after promotion.
- `release-archive-sweep` (proposed) — downstream step; cleans up old RC staging artefacts.
- `release-audit-report` (proposed) — downstream step; assembles the per-release audit record.
- [ASF release policy](https://www.apache.org/legal/release-policy.html) —
  `dist/release/` PMC-write-only rule (for `release_dist_backend = svnpubsub`); one-hour promote-to-announce wait.
- [ASF release distribution](https://infra.apache.org/release-distribution.html) — mirror propagation timing (~24 h); archive move rules.
- [`tools/release-management`](../../../../tools/release-management/README.md) —
  `release-management promote verdict` / `render`, the Step 0 verdict and the Step 2 command set.
- [`tools/release-config`](../../../../tools/release-config/README.md) —
  `release-config preflight` / `load --skill promote`.
