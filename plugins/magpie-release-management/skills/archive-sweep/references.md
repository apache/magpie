<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-archive-sweep — references

- [`docs/release-management/process.md`](../../../../docs/release-management/process.md) —
  Step 12 context.
- [`docs/release-management/spec.md`](../../../../docs/release-management/spec.md) —
  `release-archive-sweep` per-skill specification.
- [`<project-config>/release-management-config.md`](../../../magpie-setup/templates/release-management-config.md) —
  adopter keys this skill reads (`archive_retention_rule`,
  `release_dist_backend`, `release_dist_url_template`).
- `release-announce-draft` — upstream step (Step 11).
- `release-audit-report` (proposed) — downstream step (Step 13).
- [ASF release distribution § archiving](https://infra.apache.org/release-distribution.html) —
  the retention baseline ("only the latest version of each supported line").
- [archive.apache.org](https://archive.apache.org/dist/) — the ASF archive
  destination.
- [`tools/release-management`](../../../../tools/release-management/README.md) —
  `release-management archive-sweep verdict` / `listing` / `trains` / `retention` / `render`, Steps 0–2.
- [`tools/release-config`](../../../../tools/release-config/README.md) —
  `release-config preflight` / `load --skill archive-sweep`.
