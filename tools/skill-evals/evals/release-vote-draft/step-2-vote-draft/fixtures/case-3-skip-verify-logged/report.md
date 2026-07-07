<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (--skip-verify-check accepted)
product_name: Apache Airflow
version: 2.11.0
rc_number: rc3
staging_url: https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc3/
tag_url: https://github.com/apache/airflow/releases/tag/2.11.0-rc3
keys_url: https://dist.apache.org/repos/dist/release/airflow/KEYS
changelog_url: https://github.com/apache/airflow/blob/2.11.0-rc3/CHANGELOG.md
vote_list: dev@airflow.apache.org
vote_window_hours: 72
subject_template: "[VOTE] Release Apache Airflow <version> from <version>-<rcN>"
canned_body: none
expedited: false
skip_verify_logged: true
skip_verify_reason: "rc3 is identical to rc2 except for a KEYS fix; RM confirmed all artefact checksums match rc2 which passed verify."
