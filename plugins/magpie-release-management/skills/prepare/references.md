<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-prepare — references

- [`docs/release-management/process.md`](../../../../docs/release-management/process.md) —
  Steps 1, 2, and 14 context.
- [`docs/release-management/spec.md`](../../../../docs/release-management/spec.md) —
  `release-prepare` per-skill specification.
- [`docs/release-management/reproducibility.md`](../../../../docs/release-management/reproducibility.md) —
  the source-archive review (2e) buckets and rationale, and the 🪶
  ASF-specific automated-signing setup (Step A).
- [`<project-config>/release-build.md`](../../../magpie-setup/templates/release-build.md) —
  `§ Source archive` (`source_archive_method`, `export_ignore_reviewed`)
  and `§ Reproducibility checks`.
- [`projects/_template/workflows/release-candidate.yml`](../../../magpie-setup/templates/workflows/release-candidate.yml) —
  the workflow template Step A renders.
- [`tools/reproducible-archive`](../../../../tools/reproducible-archive/README.md) —
  `repro-archive build` / `compare` used for the before/after listing.
- [`<project-config>/release-management-config.md`](../../../magpie-setup/templates/release-management-config.md) —
  adopter keys this skill reads (`release_branch_base`,
  `version_manifest_files`, `category_x_dependencies`,
  `release_planning_issue_template`).
- [`<project-config>/release-trains.md`](../../../magpie-setup/templates/release-trains.md) —
  release train identity and RM roster.
- `release-keys-sync` (proposed) — downstream Step 3.
- `release-rc-cut` (proposed) — downstream Steps 4–5.
- [ASF release policy](https://www.apache.org/legal/release-policy.html), canonical.
- [ASF licensing-howto](https://www.apache.org/legal/resolved.html) —
  Category-A/B/X dependency rules; Category-X is a hard stop for this
  skill.
- [`tools/release-management`](../../../../tools/release-management/README.md#prepare) —
  `release-management prepare`: the Step 0 verdict, the planning issue, the prep and post-release PRs, the 2e review, the Step A gate and workflow.
