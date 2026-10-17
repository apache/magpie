<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-audit-report — prerequisites

- **`<version>` argument supplied.**
- **Planning issue findable** — either `--planning-issue <url>` was passed or the skill can locate a planning issue on `<upstream>` matching `<version>` in its title.
- **`<project-config>/release-management-config.md` readable** with `audit_log_path` configured.
  The optional `product_name` key supplies the human-readable product name used in the record title and PR text; it defaults to `<project>` when absent.
- **The approver roster** at `release_approver_roster_path` (default `<project-config>/pmc-roster.md`, the same key `release-vote-tally` and `release-promote` read)
  readable for binding-voter handle resolution.
