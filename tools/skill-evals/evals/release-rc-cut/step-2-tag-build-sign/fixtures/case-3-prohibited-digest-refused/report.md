<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS
version: 3.0.0
rc_number: rc2
build_command: mvn -Papache-release clean install -DskipTests
expected_artefacts:
  - apache-myproject-3.0.0-source-release.zip
  - apache-myproject-3.0.0-bin.tar.gz
digest_set: sha512
backend: github-releases
staging_url: github-releases://apache/myproject/3.0.0-rc2
signing_key_fingerprint: DEAD1234BEEF5678901234DEAD1234BEEF567890
release_branch: main

Note: The build config does NOT include md5 or sha1 in digest_set.
The two artefacts (source release + binary) must each receive a gpg
sign command and a sha512sum command in the output. No passphrase
argument must appear in any gpg command.
