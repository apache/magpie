<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC tag: 2.11.0-rc2
--post-to: not supplied

release-management-config.md:
  keys_file_url: https://dist.apache.org/repos/dist/release/airflow/KEYS
  keyserver: keys.openpgp.org
  release_dist_url_template: https://dist.apache.org/repos/dist/<bucket>/airflow/<version>/
  version_manifest_files: setup.cfg, airflow/__init__.py

release-build.md:
  expected artefact list: present
  digest set: sha512
  binary-exclude list: present
  RAT configuration: present

Note: the RC tag is parseable and the config is complete, so the staging
URL can be derived. However, the staging URL is NOT reachable — fetching
https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc2/ returns HTTP 404.
The RC has not been staged yet.
