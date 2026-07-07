<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS
Step 1 result:
  dist_backend: svnpubsub
  releases_found: [2.9.0, 2.10.0, 2.11.0]
  past_retention: [2.9.0, 2.10.0]
  orphans: []
  latest_of_each_line: {"2.x": "2.11.0"}
  handoff_required: false

Config:
  project_dist_name: airflow
  release_dist_url_template: https://dist.apache.org/repos/dist/release/airflow/<version>
  archive_url_template: https://archive.apache.org/dist/airflow/<version>
