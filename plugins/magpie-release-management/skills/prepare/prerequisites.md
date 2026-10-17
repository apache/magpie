<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-prepare — prerequisites

- **`<project-config>/release-trains.md` readable** — identifies the release train, release branch, and release manager for `<version>`.
- **`<project-config>/release-management-config.md` readable** —
  provides `release_branch_base`, `version_manifest_files`, `category_x_dependencies`, and `release_planning_issue_template`
  (optional: `changelog_file`, and `changelog_label_categories` as `LABEL=SECTION` entries for 2d).
- **`<upstream>` access** — read access to the upstream repo to list merged PRs via `gh pr list` since the previous release tag.

For Step 2 (`prep`):
- **Planning issue open and labelled `release-planning`** — confirms Step 1 completed.
  The skill can also accept `--planning-issue <url>`.

For Step 14 (`post`):
- **Planning issue labelled `announced`** — confirms Steps 10–11 completed. Accepted via `--planning-issue <url>`.

For Step 2's source-archive review (`prep`, Step 2e) — optional:
- **`<project-config>/release-build.md § Source archive`** — `source_archive_method` (default `git-archive`) and `export_ignore_reviewed`.
  Absent file or key = the review has not happened yet, which is exactly when the sub-step runs.
- **A local clone of `<upstream>`** at the release branch tip (the resolved `user.md` clone path) —
  the review lists what `git archive` would ship from *that* tree.

For Step A (`automated-signing`, 🪶 ASF-specific):
- **The project's organization offers it.** The organization manifest key `release_process.automated_signing`,
  resolved `project.md` → organization manifest → framework default (not offered), is set;
  of the shipped organizations only [`organizations/ASF/organization.md`](../../../../organizations/ASF/organization.md) sets it.
  The sub-command is not offered otherwise.
- **`release-build.md § Reproducibility checks`** — `reproducibility_source: on` and `reproducibility_binaries: byte-identical` (or no binaries).
