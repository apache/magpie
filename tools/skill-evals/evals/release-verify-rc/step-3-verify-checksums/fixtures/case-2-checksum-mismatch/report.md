<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md digest set: sha512, sha256

Artefacts and digest files present:
  apache-airflow-2.11.0-source-release.tar.gz
  apache-airflow-2.11.0-source-release.tar.gz.sha512  — sha512sum --check: OK
  apache-airflow-2.11.0-source-release.tar.gz.sha256  — sha256sum --check: OK
  apache-airflow-2.11.0-bin.tar.gz
  apache-airflow-2.11.0-bin.tar.gz.sha512  — sha512sum --check: FAILED
    (reported hash: abc123...; computed hash: def456... — mismatch)
  apache-airflow-2.11.0-bin.tar.gz.sha256  — sha256sum --check: OK

No .md5 files found in the staging directory.
