<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-promote — prerequisites

- **Planning issue carries `vote-passed`** — the tally step has confirmed the vote passed.
  `--planning-issue <url>` points at the issue directly.
- **`[RESULT] [VOTE]` archive URL on the planning issue** — used in the svn commit message; pass `--result-vote-url <url>` if the issue does not record it.
- **`<project-config>/release-management-config.md` readable** — required keys: `release_dist_backend`, `release_dist_url_template`.
- **Approver roster readable** — the file at `release_approver_roster_path` (default `<project-config>/pmc-roster.md`), to check PMC membership of the current RM;
  skipped when `non_asf` is true (`project.md` does not declare `organization: ASF`), where PMC concepts do not apply.
- **RM identity known** — from the resolved `user.md` (field `release_manager.github_handle` or `release_manager.apache_id`).
