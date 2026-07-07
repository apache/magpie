<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (skip-promote-wait override accepted)
product_name: Apache Airflow
version: 2.11.0
promote_timestamp: 2026-06-11 09:45 UTC
dist_release_url: https://dist.apache.org/repos/dist/release/airflow/2.11.0/
download_page_url: https://airflow.apache.org/docs/apache-airflow/2.11.0/installation/installing-from-pypi.html
changelog_url: https://github.com/apache/airflow/blob/2.11.0/CHANGELOG.md
keys_url: https://dist.apache.org/repos/dist/release/airflow/KEYS
announce_list: announce@apache.org
announce_cc_lists: dev@airflow.apache.org, users@airflow.apache.org
subject_template: "[ANNOUNCE] Apache Airflow <version> released"
release_announce_backend: announce-list
canned_body: none
--skip-promote-wait passed with reason: "Critical security release; mirrors propagated within 30 minutes per infra confirmation."
