<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight passed. Sub-command: prep. Version: 2.11.0.
Planning issue: apache/airflow#48700 (labelled release-planning)
Previous tag: 2.10.3. Release branch base: main.

version_manifest_files: setup.cfg, airflow/__init__.py
  Current version: 2.11.0.dev0 → target: 2.11.0

category_x_dependencies: (empty — no Category-X violations)

NOTICE diff vs 2.10.3:
  REMOVED attribution: "This product includes software developed by
    The Jackson Project (https://github.com/FasterXML/jackson)."

  Dependency scan: jackson-databind 2.15.3 is still listed in
  setup.cfg (install_requires). The dependency was NOT removed;
  the attribution removal has no justification.

Do not open a prep PR. Surface the unjustified NOTICE removal to the RM.
