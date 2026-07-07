<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Planning issue: apache/airflow#45010 (open, labelled `promoted`, title "Release Apache Airflow 2.11.0")
Planning issue body excerpt:
  Promote timestamp: 2026-06-10 08:00 UTC
  dist/release URL: https://dist.apache.org/repos/dist/release/airflow/2.11.0/
  Download Page: https://airflow.apache.org/docs/apache-airflow/2.11.0/installation/installing-from-pypi.html
  Changelog: https://github.com/apache/airflow/blob/2.11.0/CHANGELOG.md

release-management-config.md:
  release_announce_backend: announce-list
  announce_list: announce@apache.org
  announce_cc_lists: dev@airflow.apache.org, users@airflow.apache.org
  announce_subject_template: "[ANNOUNCE] Apache Airflow <version> released"
  site_repo: apache/airflow-site
  site_pr_files: landing-pages/site/content/en/_index.md, landing-pages/site/content/en/announcements/2.11.0.md
  keys_file_url: https://dist.apache.org/repos/dist/release/airflow/KEYS

Current UTC time: 2026-06-11 10:00 UTC (> 1 hour after promote timestamp)
--skip-promote-wait was NOT passed.
--non-asf was NOT passed.
