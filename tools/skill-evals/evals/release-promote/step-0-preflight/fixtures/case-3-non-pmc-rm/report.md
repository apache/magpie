<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Trigger: /release-promote 2.11.0-rc1
--planning-issue was NOT passed (auto-detect).
--non-asf was NOT passed.

Planning issue: apache/airflow#45010 (open, labelled `vote-passed`, title "Release Apache Airflow 2.11.0")
Planning issue body excerpt:
  Staging URL: https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/
  [RESULT] [VOTE] archive: https://lists.apache.org/thread/some-result-thread-id

release-management-config.md:
  release_dist_backend: svnpubsub
  release_dist_url_template: https://dist.apache.org/repos/dist/<bucket>/airflow/<version>/

pmc-roster.md excerpt (no entry for the current RM):
  - handle: alicepmc
    apache_id: alicepmc
    binding: true
  - handle: bobpmc
    apache_id: bobpmc
    binding: true

Resolved RM identity (from user.md): apache_id = johndoe
Note: johndoe does not appear in pmc-roster.md. johndoe is an Apache committer
but is not listed as a PMC member.

Target URL check: https://dist.apache.org/repos/dist/release/airflow/2.11.0/ — directory does not exist (svn: E200009)
