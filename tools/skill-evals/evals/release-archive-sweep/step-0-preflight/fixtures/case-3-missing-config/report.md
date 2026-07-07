<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-management-config.md:
  release_dist_backend: github-releases
  release_dist_url_template: https://github.com/example-org/myproject/releases/tag/<version>
  archive_retention_rule: keep latest of each supported train only
  project_dist_name: myproject
  NOTE: archive_url_template key is ABSENT (no archive URL configured for github-releases backend).

release-trains.md:
  NOT FOUND — the file does not exist in the project-config directory.

--planning-issue was NOT passed.
