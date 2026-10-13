<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-announce-draft — prerequisites

- **Planning issue carries `promoted`**, confirming Step 10 (promote) completed; `--planning-issue <url>` names it explicitly.
- **Promote timestamp available** — the UTC timestamp of the Step 10 promote commit (`svn mv` for `release_dist_backend = svnpubsub`, or the backend's equivalent) is in the planning issue body, or the RM gives it via `--promote-timestamp <ISO-8601>`.
- **`<project-config>/release-management-config.md` readable** — `announce_list`, `announce_cc_lists`, `announce_subject_template`, `site_repo`, `site_pr_files`, `release_announce_backend`.
- **Download Page URL available** — in the planning issue body, in `release-management-config.md`, or via `--download-page <url>`.
