<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md binary-exclude list: *.class (listed as expected/known binary)

Note: *.jar is NOT in the binary-exclude list — jar files are prohibited in this source artefact.

Scan of unpacked apache-airflow-2.11.0-source-release.tar.gz:
  Files with prohibited extensions found:
    airflow/vendor/some-lib/some-lib-1.0.jar   (*.jar — prohibited, not in binary-exclude list)

  Files listed as EXPECTED-BINARY in release-build.md:
    (none with *.class extension found either)
