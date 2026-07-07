<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-management-config.md:
  release_dist_backend: svnpubsub
  release_dist_url_template: https://dist.apache.org/repos/dist/release/airflow/<version>/
  archive_url_template: https://archive.apache.org/dist/airflow/<version>/
  project_dist_name: airflow
  NOTE: archive_retention_rule key is ABSENT from the file.

release-trains.md:
  - train: "2.x", supported: true, latest: "2.11.0"

--planning-issue was NOT passed.
