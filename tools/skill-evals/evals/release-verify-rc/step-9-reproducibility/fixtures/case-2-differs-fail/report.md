<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC: 2.4.0-rc1. Staged: https://dist.apache.org/repos/dist/dev/foo/2.4.0-rc1/
Flags: (none)

release-management-config.md: automated_release_signing: off
release-build.md:
  source_archive_method: git-archive, source_archive_format: zip,
  source_archive_prefix: apache-foo-2.4.0
  reproducibility_source: on
  reproducibility_binaries: off

Planning-issue reproducibility record:
  commit a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
  SOURCE_DATE_EPOCH 1758400000

Voter's run:
  git rev-parse 2.4.0-rc1^{commit} → a1b2c3d4e5f60718293a4b5c6d7e8f9012345678 (matches)
  repro-archive check apache-foo-2.4.0-source.zip --epoch 1758400000
    → FAIL modification-times (3 distinct timestamps); FAIL zip-extra-fields
  repro-archive compare apache-foo-2.4.0-source.zip rebuilt/apache-foo-2.4.0-source.zip
    → verdict differs
       added   apache-foo-2.4.0/src/foo/__pycache__/core.cpython-312.pyc
       added   apache-foo-2.4.0/.env.local
       changed apache-foo-2.4.0/src/foo/version.py
