<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare automated-signing
Project: Apache Foo (project.md → organization: ASF)

organizations/ASF/organization.md → release_process.automated_signing:
  policy_url: https://infra.apache.org/release-signing.html#automated-release-signing
  key_request_channel: infra-jira, approval_body: security@apache.org

release-management-config.md:
  release_branch_base: main
  release_dist_backend: svnpubsub
  release_vote_backend: atr
  version_manifest_files: pom.xml
  category_x_dependencies: (empty)
  automated_release_signing: off

release-build.md: source_archive_method git-archive, reproducibility_source: on,
  reproducibility_binaries: byte-identical (one convenience binary).

release-trains.md contains an entry for the 3.x train, Release Manager: @jdoe.
gh pr list access confirmed: apache/foo responds.
No .apache-magpie.local.lock drift. No override file.
