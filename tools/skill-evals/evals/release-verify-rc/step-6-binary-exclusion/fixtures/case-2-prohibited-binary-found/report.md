<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md Binary-exclude list (known-accepted): *.class
(no additional scan globs beyond the fixed baseline)

Note: *.jar is NOT marked known-and-accepted — jar files matching the
fixed baseline are prohibited in this source artefact.

Scan of unpacked apache-airflow-2.11.0-source-release.tar.gz:
  Files with prohibited extensions found:
    airflow/vendor/some-lib/some-lib-1.0.jar   (*.jar — prohibited, not known-accepted)

  Files listed as EXPECTED-BINARY in release-build.md:
    (none with *.class extension found either)
