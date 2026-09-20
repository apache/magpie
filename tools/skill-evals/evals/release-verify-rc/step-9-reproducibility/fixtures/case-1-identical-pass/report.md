<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC: 1.0.0-rc1. Staged: https://dist.apache.org/repos/dist/dev/foo/1.0.0-rc1/
Flags: (none — no --skip-repro, no --trusted-hardware)

release-management-config.md: automated_release_signing: off
release-build.md:
  source_archive_method: git-archive, source_archive_format: tar.gz,
  source_archive_prefix: apache-foo-1.0.0
  reproducibility_source: on
  reproducibility_binaries: off

Planning-issue reproducibility record (from release-rc-cut):
  repository https://github.com/apache/foo
  commit 1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12
  swhid_dir swh:1:dir:3b9f0c2e7a1d4f6b8e0a2c4d6f8a0b2c4e6f8a1b;origin=https://github.com/apache/foo;anchor=swh:1:rev:1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12
  SOURCE_DATE_EPOCH 1758326400
  sha512 3f2a…9c (apache-foo-1.0.0-source.tar.gz)

Voter ran the recipe on their own laptop:
  git rev-parse 1.0.0-rc1^{commit} → 1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12 (matches)
  git tag -v 1.0.0-rc1 → Good signature (key in KEYS)
  repro-archive check apache-foo-1.0.0-source.tar.gz --epoch 1758326400 \
    --swhid swh:1:dir:3b9f0c2e7a1d4f6b8e0a2c4d6f8a0b2c4e6f8a1b → all PASS
    (swhid: content is swh:1:dir:3b9f0c2e7a1d4f6b8e0a2c4d6f8a0b2c4e6f8a1b)
  repro-archive build … --epoch 1758326400 -o rebuilt/apache-foo-1.0.0-source.tar.gz
  repro-archive compare apache-foo-1.0.0-source.tar.gz rebuilt/apache-foo-1.0.0-source.tar.gz
    → verdict identical (sha512 equal)
