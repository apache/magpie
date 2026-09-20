<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC: 0.2.0-rc1. Staged: https://dist.apache.org/repos/dist/dev/magpie/0.2.0-rc1/
Flags: (none)

release-management-config.md: automated_release_signing: off
release-build.md:
  source_archive_method: git-archive, source_archive_format: zip,
  source_archive_prefix: apache-magpie-0.2.0
  reproducibility_source: on
  reproducibility_binaries: off

Planning-issue reproducibility record:
  commit 0f1e2d3c4b5a69788796a5b4c3d2e1f0aabbccdd
  SOURCE_DATE_EPOCH 1758500000
  note: RM built with a plain `git archive --format=zip` (git 2.44), not repro-archive

Voter's run (git 2.55):
  git rev-parse 0.2.0-rc1^{commit} → 0f1e2d3c4b5a69788796a5b4c3d2e1f0aabbccdd (matches)
  repro-archive check apache-magpie-0.2.0-source.zip --epoch 1758500000
    → FAIL zip-extra-fields (every member carries a 9-byte extra field)
  repro-archive compare apache-magpie-0.2.0-source.zip rebuilt/apache-magpie-0.2.0-source.zip
    → verdict content-identical
       metadata reproducibility check zip-extra-fields fails on A
       metadata compression or container bytes differ (same members, same modes)
