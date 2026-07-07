<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS
version: 2.12.0
rc_number: rc1
build_command: mvn -Papache-release clean install
expected_artefacts:
  - apache-myproject-2.12.0-source-release.zip
  - apache-myproject-2.12.0-bin.tar.gz
digest_set: sha512, sha256
backend: svnpubsub
staging_url: https://dist.apache.org/repos/dist/dev/myproject/2.12.0-rc1/
signing_key_fingerprint: ABCD1234EF5678901234ABCD1234EF5678901234
release_branch: main
