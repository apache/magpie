<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC tag: 2.11.0-rc1
--post-to: not supplied

release-management-config.md:
  keys_file_url: https://dist.apache.org/repos/dist/release/airflow/KEYS
  keyserver: keys.openpgp.org
  release_dist_url_template: https://dist.apache.org/repos/dist/<bucket>/airflow/<version>/
  version_manifest_files: setup.cfg, airflow/__init__.py

release-build.md:
  expected artefact list: present (apache-airflow-2.11.0-source-release.tar.gz, apache-airflow-2.11.0-bin.tar.gz)
  digest set: sha512, sha256
  binary-exclude list: present (*.class, *.jar)
  RAT configuration: pom.xml § rat-maven-plugin, rat-excludes.txt

Staging URL derivation: substituting bucket=dev, version=2.11.0 into template yields
  https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/
