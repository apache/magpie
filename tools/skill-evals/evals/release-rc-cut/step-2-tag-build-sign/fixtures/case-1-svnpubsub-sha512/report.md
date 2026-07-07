<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS
version: 2.12.0
rc_number: rc1
build_command: python -m build --sdist
expected_artefacts: apache_airflow-2.12.0.tar.gz
digest_set: sha512
backend: svnpubsub
staging_url: https://dist.apache.org/repos/dist/dev/airflow/2.12.0-rc1/
signing_key_fingerprint: ABCD1234EF5678901234ABCD1234EF5678901234
release_branch: main
