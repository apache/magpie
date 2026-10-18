<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-announce-draft — references

- [`docs/release-management/process.md`](../../../../docs/release-management/process.md) —
  Step 11 context.
- [`docs/release-management/spec.md`](../../../../docs/release-management/spec.md) —
  `release-announce-draft` per-skill specification.
- [`<project-config>/release-management-config.md`](../../../magpie-setup/templates/release-management-config.md) —
  adopter keys this skill reads (`announce_list`, `announce_cc_lists`,
  `announce_subject_template`, `site_repo`, `site_pr_files`,
  `release_announce_backend`).
- `release-promote` (proposed) — upstream step; `promoted` label is the
  completion signal.
- `release-archive-sweep` (proposed) — downstream step; cleans up RC
  artefacts from the staging area.
- `release-audit-report` (proposed) — downstream step; records the
  complete lifecycle.
- [ASF release policy § announcements](https://www.apache.org/legal/release-policy.html#release-announcements) —
  the `<announce-list>` requirement for ASF releases (see `release_announce_backend`).
- [ASF release distribution](https://infra.apache.org/release-distribution.html) —
  the `closer.lua` CDN/mirror selector requirement for download links.
- [`tools/release-management`](../../../../tools/release-management/README.md) —
  `release-management announce-draft verdict` / `render --step 2|3`, the Step 0 verdict, the draft and the site-bump PR.
- [`tools/release-config`](../../../../tools/release-config/README.md) —
  `release-config preflight` / `load --skill announce-draft`.
