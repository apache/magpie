<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-management-config.md:
  release_dist_backend: atr
  release_dist_url_template: https://dist.apache.org/repos/dist/release/magpie/<version>/
  archive_retention_rule: latest_of_each_supported_line
  archive_url_template: https://archive.apache.org/dist/magpie/
  project_dist_name: magpie

release-trains.md:
  - train: "0.x", supported: true, latest: "0.2.0"

--planning-issue was NOT passed.
