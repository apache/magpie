<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS
dist_backend: svnpubsub

release-trains.md:
  - train: "2.x", supported: true, latest: "2.11.0"
  - train: "3.x", supported: true, latest: "3.0.1"

archive_retention_rule: keep latest of each supported train only

Current svn list output for dist/release/airflow/:
  2.9.0/
  2.10.0/
  2.11.0/
  3.0.0/
  3.0.1/
