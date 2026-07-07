<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Planning issue: https://github.com/apache/airflow/issues/45100 (closed)
Title: "Release Apache Airflow 2.10.3"

Planning issue body:
  RC: rc2
  [VOTE] thread: https://lists.apache.org/thread/vote-airflow-2.10.3-rc2
  # [RESULT] thread URL was not recorded on the planning issue
  RC artefacts:
    - apache-airflow-2.10.3.tar.gz  sha512: 112233...  sig: apache-airflow-2.10.3.tar.gz.asc
  # SVN promote revision was not recorded
  # [ANNOUNCE] archive URL was not recorded

pmc-roster.md: entries present but [RESULT] thread is missing so
binding-voter details cannot be extracted.

release-management-config.md:
  audit_log_path: audit-logs/releases
  release_approver_roster_path: projects/airflow/pmc-roster.md
