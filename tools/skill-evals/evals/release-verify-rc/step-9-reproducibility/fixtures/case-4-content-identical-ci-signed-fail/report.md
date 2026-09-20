<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC: 3.2.0-rc2. Project: Apache Foo (project.md → organization: ASF).
Staged in ATR by the release-candidate workflow.
Flags: --skip-repro --trusted-hardware --post-to https://github.com/apache/foo/issues/300

release-management-config.md: automated_release_signing: enabled
release-build.md:
  source_archive_method: git-archive, source_archive_format: tar.gz,
  source_archive_prefix: apache-foo-3.2.0
  reproducibility_source: on
  reproducibility_binaries: byte-identical
  binary_rebuild_command: mvn -Papache-release -Dproject.build.outputTimestamp="${SOURCE_DATE_EPOCH}" clean package
  expected_artefacts: apache-foo-3.2.0-source.tar.gz, apache-foo-3.2.0-bin.tar.gz

Planning-issue reproducibility record (from the CI run):
  commit 9988776655443322110000ffeeddccbbaa998877
  SOURCE_DATE_EPOCH 1758412800

Committer's run on their own workstation:
  git rev-parse 3.2.0-rc2^{commit} → 9988776655443322110000ffeeddccbbaa998877 (matches)
  repro-archive compare apache-foo-3.2.0-source.tar.gz rebuilt/apache-foo-3.2.0-source.tar.gz
    → verdict content-identical
       metadata reproducibility check gzip-header fails on A (embedded filename)
  cmp apache-foo-3.2.0-bin.tar.gz target/apache-foo-3.2.0-bin.tar.gz → identical
