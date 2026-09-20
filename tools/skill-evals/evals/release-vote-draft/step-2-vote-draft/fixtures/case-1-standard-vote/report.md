<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (no overrides)
product_name: Apache Airflow
version: 2.11.0
rc_number: rc1
staging_url: https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/
tag_url: https://github.com/apache/airflow/releases/tag/2.11.0-rc1
keys_url: https://dist.apache.org/repos/dist/release/airflow/KEYS
changelog_url: https://github.com/apache/airflow/blob/2.11.0-rc1/CHANGELOG.md
vote_list: dev@airflow.apache.org
vote_window_hours: 72
subject_template: "[VOTE] Release Apache Airflow <version> from <version>-<rcN>"
canned_body: none
expedited: false
skip_verify_logged: false
repro_record: commit 1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12, SOURCE_DATE_EPOCH 1758326400, sha512 3f2a9c…e1 (apache_airflow-2.11.0.tar.gz)
verification_doc_url: https://github.com/apache/airflow/blob/2.11.0-rc1/docs/verifying-a-release-candidate.md
reproducibility_doc_url: https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md
verification_skill: magpie-release-management:verify-rc
vote_backend: manual
signing_mode: rm-key
