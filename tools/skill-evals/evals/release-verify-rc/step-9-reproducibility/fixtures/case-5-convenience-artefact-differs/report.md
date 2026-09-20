<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC: 4.1.0-rc2. Staged: https://dist.apache.org/repos/dist/dev/foo/4.1.0-rc2/
Flags: (none)

release-management-config.md: automated_release_signing: off
release-build.md:
  source_archive_method: git-archive, source_archive_format: tar.gz,
  source_archive_prefix: apache-foo-4.1.0
  reproducibility_source: on
  reproducibility_binaries: byte-identical
  § Convenience artefacts (project-specific):
    - apache-foo-4.1.0-bin.tar.gz (binary-tarball, staging dist-dev,
      build_command: mvn -Papache-release -Dproject.build.outputTimestamp="${SOURCE_DATE_EPOCH}" -DskipTests clean package)
    - registry.example.org/apache/foo:4.1.0-rc2 (container-image, staging registry-staging,
      build_command: docker build --build-arg SOURCE_DATE_EPOCH -t registry.example.org/apache/foo:4.1.0-rc2 .)

Planning-issue reproducibility record:
  commit 9988776655443322110000ffeeddccbbaa998877
  SOURCE_DATE_EPOCH 1758412800

Voter's run on their own workstation:
  git rev-parse 4.1.0-rc2^{commit} → 9988776655443322110000ffeeddccbbaa998877 (matches)
  repro-archive compare apache-foo-4.1.0-source.tar.gz rebuilt/apache-foo-4.1.0-source.tar.gz
    → verdict identical
  cmp apache-foo-4.1.0-bin.tar.gz target/apache-foo-4.1.0-bin.tar.gz → identical
  docker pull registry.example.org/apache/foo@sha256:1111… (staged digest); local rebuild digest sha256:2222…
    → DIFFERS: registry.example.org/apache/foo:4.1.0-rc2 (base image not pinned by digest; layer 0 differs)
