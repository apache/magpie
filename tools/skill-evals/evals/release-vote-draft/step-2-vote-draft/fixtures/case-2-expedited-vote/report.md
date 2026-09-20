<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (--expedited accepted)
product_name: Apache Airflow
version: 2.10.4
rc_number: rc1
staging_url: https://dist.apache.org/repos/dist/dev/airflow/2.10.4-rc1/
tag_url: https://github.com/apache/airflow/releases/tag/2.10.4-rc1
keys_url: https://dist.apache.org/repos/dist/release/airflow/KEYS
changelog_url: https://github.com/apache/airflow/blob/2.10.4-rc1/CHANGELOG.md
vote_list: dev@airflow.apache.org
vote_window_hours: 48
subject_template: "[VOTE] Release Apache Airflow <version> from <version>-<rcN>"
canned_body: none
expedited: true
expedited_reason: "Critical security fix for CVE-2026-12345; abbreviated window approved by PMC chair."
skip_verify_logged: false
repro_record: commit a1b2c3d4e5f60718293a4b5c6d7e8f9012345678, SOURCE_DATE_EPOCH 1758400000, sha512 77ab…10 (apache_airflow-2.10.4.tar.gz)
verification_doc_url: https://github.com/apache/airflow/blob/2.10.4-rc1/docs/verifying-a-release-candidate.md
reproducibility_doc_url: https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md
verification_skill: magpie-release-management:verify-rc
vote_backend: manual
signing_mode: rm-key
repro_record (cont.): repository https://github.com/apache/airflow; swhid_dir swh:1:dir:9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c;origin=https://github.com/apache/airflow;anchor=swh:1:rev:a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
