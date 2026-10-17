<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-archive-sweep — prerequisites

- **`<project-config>/release-management-config.md` readable** — `archive_retention_rule`, `release_dist_backend`, `release_dist_url_template`,
  and the archive destination: `archive_url_template`, which defaults to `https://archive.apache.org/dist/<project>/` (from `project_dist_name`) for both ASF backends, `svnpubsub` and `atr`,
  and is required for any other backend.
- **`<project-config>/release-trains.md` readable** — the supported release lines and their current latest versions; used to identify orphans.
- **Distribution listing accessible** — the list of releases currently on `dist/release/<project>/` (for `release_dist_backend = svnpubsub`, or the backend equivalent).
  For `svnpubsub`, this is an `svn list` call against the distribution URL.
