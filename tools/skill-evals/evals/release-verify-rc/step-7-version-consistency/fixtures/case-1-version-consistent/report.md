<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC tag: 2.11.0-rc1 → expected version: 2.11.0

version_manifest_files (from release-management-config.md): setup.cfg, airflow/__init__.py

Extracted version strings:
  setup.cfg:
    [metadata] section → version = 2.11.0
  airflow/__init__.py:
    __version__ = "2.11.0"

Both manifest files report 2.11.0, which matches the expected version exactly.
