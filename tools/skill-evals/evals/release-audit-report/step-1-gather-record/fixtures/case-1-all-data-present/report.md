<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Planning issue: https://github.com/apache/airflow/issues/45200 (closed)
Title: "Release Apache Airflow 2.11.0"

Planning issue body:
  RC: rc1
  [VOTE] thread: https://lists.apache.org/thread/vote-airflow-2.11.0-rc1
  [RESULT] thread: https://lists.apache.org/thread/result-airflow-2.11.0-rc1
  RC artefacts:
    - apache-airflow-2.11.0.tar.gz  sha512: aabbcc...  sig: apache-airflow-2.11.0.tar.gz.asc
    - apache_airflow-2.11.0-py3-none-any.whl  sha512: ddeeff...  sig: apache_airflow-2.11.0-py3-none-any.whl.asc
  SVN promote revision: r12345
  [ANNOUNCE] archive URL: https://lists.apache.org/thread/announce-airflow-2.11.0

[RESULT] thread summary (from ponymail archive):
  Binding +1: 4 (from pmc-roster.md handles: @committerA, @committerB, @committerC, @committerD)
  Binding -1: 0

pmc-roster.md: entries for @committerA, @committerB, @committerC, @committerD confirmed

release-management-config.md:
  audit_log_path: audit-logs/releases
  release_approver_roster_path: projects/airflow/pmc-roster.md
