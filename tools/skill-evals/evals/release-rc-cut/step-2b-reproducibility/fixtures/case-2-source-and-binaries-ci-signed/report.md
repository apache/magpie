<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Step 2 emitted. Project: Apache Foo (project.md → organization: ASF).

Loaded configuration:
  version: 3.2.0, rc: rc2
  expected_artefacts:
    apache-foo-3.2.0-source.tar.gz  (canonical source)
    apache-foo-3.2.0-bin.tar.gz     (convenience binary)
  build_command: mvn -Papache-release -Dproject.build.outputTimestamp="${SOURCE_DATE_EPOCH}" clean package
  source_archive_method: git-archive
  source_archive_format: tar.gz
  source_archive_prefix: apache-foo-3.2.0
  reproducibility_source: on
  reproducibility_binaries: byte-identical
  convenience_artefacts (project-specific):
    - name: apache-foo-3.2.0-bin.tar.gz, kind: binary-tarball, staging: dist-dev,
      reproducibility: byte-identical, publish_channel: dist-release,
      build_command: mvn -Papache-release -Dproject.build.outputTimestamp="${SOURCE_DATE_EPOCH}" clean package
  signing_mode: ci-automated   (release-management-config.md: automated_release_signing: enabled)
  --skip-repro-check: passed by the RM ("skip it, CI checks anyway")
  SOURCE_DATE_EPOCH from Step 2: 1758412800
