<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-audit-report — references

- [`audit-record-schema.md`](audit-record-schema.md) — canonical required-field schema and privacy boundary for audit records;
  the schema-validation step in Step 2 reads from here.
- [`docs/release-management/process.md`](../../../../docs/release-management/process.md) — Step 13 context.
- [`docs/release-management/spec.md`](../../../../docs/release-management/spec.md) — `release-audit-report` per-skill specification and privacy boundary.
- [`<project-config>/release-management-config.md`](../../../magpie-setup/templates/release-management-config.md) —
  `audit_log_path` and `release_approver_roster_path` keys this skill reads.
- [`<project-config>/pmc-roster.md`](../../../magpie-setup/templates/pmc-roster.md) — authoritative handle source for binding-voter citations.
- [`tools/release-management`](../../../../tools/release-management/README.md) —
  `release-management audit-report verdict` / `gather` / `voters` / `check` / `record` / `pr`.
- [`tools/release-config`](../../../../tools/release-config/README.md) —
  `release-config preflight` / `load --skill audit-report`.
- `release-archive-sweep` — upstream step; Step 12 cleans up RC artefacts.
- `release-announce-draft` — provides `[ANNOUNCE]` archive URL.
- `release-promote` — provides the promote revision.
