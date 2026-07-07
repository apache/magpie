<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-management-config.md:
  release_dist_backend: svnpubsub
  release_dist_url_template: https://dist.apache.org/repos/dist/release/airflow/<version>/
  archive_retention_rule: keep latest of each supported train only
  archive_url_template: https://archive.apache.org/dist/airflow/<version>/
  project_dist_name: airflow

release-trains.md:
  - train: "2.x", supported: true, latest: "2.11.0"
  - train: "3.x", supported: true, latest: "3.0.0"

--planning-issue was NOT passed.
