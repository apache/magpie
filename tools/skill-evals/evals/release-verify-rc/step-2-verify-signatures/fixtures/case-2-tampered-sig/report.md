<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC inventory from Step 1 (PASS):
  apache-airflow-2.11.0-source-release.tar.gz (FOUND)
  apache-airflow-2.11.0-source-release.tar.gz.asc (FOUND)
  apache-airflow-2.11.0-bin.tar.gz (FOUND)
  apache-airflow-2.11.0-bin.tar.gz.asc (FOUND)

GPG verification results:
  apache-airflow-2.11.0-source-release.tar.gz.asc:
    gpg --verify exits 0
    Signing fingerprint: ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234
    Fingerprint ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234 IS present in the project KEYS file

  apache-airflow-2.11.0-bin.tar.gz.asc:
    gpg --verify exits NON-ZERO (exit code 2)
    Output: "gpg: BAD signature from ..."
    The binary artefact appears to have been modified after signing, or the .asc file
    does not match this binary.
