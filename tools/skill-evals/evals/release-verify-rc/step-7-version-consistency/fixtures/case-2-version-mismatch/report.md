<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC tag: 2.11.0-rc1 → expected version: 2.11.0

version_manifest_files (from release-management-config.md): setup.cfg, airflow/__init__.py

Extracted version strings:
  setup.cfg:
    [metadata] section → version = 2.11.0
  airflow/__init__.py:
    __version__ = "2.11.0.dev0"

Note: airflow/__init__.py still carries the dev suffix "2.11.0.dev0" which was
not updated to "2.11.0" before the RC was cut. This is a version-string mismatch.
