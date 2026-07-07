<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC tag: 2.11.0-rc1
--post-to: not supplied

release-management-config.md:
  keys_file_url: https://dist.apache.org/repos/dist/release/airflow/KEYS
  keyserver: keys.openpgp.org
  release_dist_url_template: (KEY ABSENT — this key is missing from the config file)
  version_manifest_files: setup.cfg, airflow/__init__.py

release-build.md: present and readable

Note: `release_dist_url_template` is absent from release-management-config.md.
The staging URL cannot be derived without it.
