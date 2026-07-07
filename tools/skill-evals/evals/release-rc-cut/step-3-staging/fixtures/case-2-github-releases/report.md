<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS
Step 2 commands confirmed by RM.
version: 3.0.0
rc_number: rc1
expected_artefacts:
  - apache-myproject-3.0.0-source-release.zip
  - apache-myproject-3.0.0-source-release.zip.asc
  - apache-myproject-3.0.0-source-release.zip.sha512
backend: github-releases
staging_url: github-releases://apache/myproject/3.0.0-rc1
release-management-config.md:
  release_dist_backend: github-releases
  release_dist_url_template: github-releases://apache/myproject/<version>-<rcN>
