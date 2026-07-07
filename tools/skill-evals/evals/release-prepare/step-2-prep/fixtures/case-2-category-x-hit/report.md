<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight passed. Sub-command: prep. Version: 2.11.0.
Planning issue: apache/airflow#48700 (labelled release-planning)
Previous tag: 2.10.3. Release branch base: main.

version_manifest_files: setup.cfg, airflow/__init__.py
  Current version: 2.11.0.dev0 → target: 2.11.0

category_x_dependencies from release-management-config.md:
  - "com.example:gpl-licensed-lib"   (GPL-2.0, Category-X)
  - "org.acme:cc-by-nc-widget"       (CC-BY-NC, Category-X)

Dependency scan of setup.cfg found:
  Line 47: install_requires includes "cc-by-nc-widget>=1.2.0"
  This matches the Category-X identifier "org.acme:cc-by-nc-widget" in
  the denylist.

Do not open a prep PR. Surface the Category-X violation to the RM.
