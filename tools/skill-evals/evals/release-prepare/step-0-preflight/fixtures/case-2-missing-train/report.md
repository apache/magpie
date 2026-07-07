<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare 3.0.0

release-management-config.md:
  release_branch_base: main
  version_manifest_files: setup.cfg, airflow/__init__.py
  category_x_dependencies: (empty)

release-trains.md: Contains only a 2.x train entry. No entry exists
  for version 3.0.0 or any 3.x train.

gh pr list access confirmed: apache/airflow responds.
