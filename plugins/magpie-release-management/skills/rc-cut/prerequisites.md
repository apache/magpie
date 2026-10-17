<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-rc-cut — prerequisites

- **Prep PR merged** — the version-bump + changelog PR opened by `release-prepare prep` must be merged into the release branch.
  The skill checks that the prep-PR label (`prep-pr-open`) is absent or that the PR is in `merged` state.
- **RC tag must not exist** — the tag `<version>-<rcN>` must not already exist on the remote;
  if it does, the skill blocks and the RM decides whether to bump the RC or delete the existing tag.
- **`<project-config>/release-build.md` readable** — `build_command`, `expected_artefacts`, `digest_set`, optional `binary_exclude_list`;
  `§ Source archive` (`source_archive_method`, `source_archive_format`, `source_archive_prefix`, `export_ignore_reviewed`) and
  `§ Reproducibility checks` (`reproducibility_source`, `reproducibility_binaries`, `binary_rebuild_command`).
- **`<project-config>/release-management-config.md` readable** — `release_dist_backend`, `release_dist_url_template`, optional `release_publish_command_template`;
  `§ Signing › automated_release_signing` (🪶 ASF-specific; read only when the project's organization offers automated signing —
  the organization manifest key `release_process.automated_signing`, resolved `project.md` → organization manifest → framework default).
- **`.gitattributes` reviewed** — when `source_archive_method` is `git-archive`, `export_ignore_reviewed` is set
  (the first-release review in `release-prepare prep` Step 2e has landed and is in the tree the tag will point at).
