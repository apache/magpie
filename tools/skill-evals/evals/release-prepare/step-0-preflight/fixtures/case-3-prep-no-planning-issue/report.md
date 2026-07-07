<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare prep 2.11.0
(no --planning-issue flag provided)

release-management-config.md:
  release_branch_base: main
  version_manifest_files: setup.cfg, airflow/__init__.py
  category_x_dependencies: (empty)

release-trains.md: Entry for 2.x train, version 2.11.0 present.

gh issue list search on apache/airflow: no open issue with label
  "release-planning" and "2.11.0" in the title was found.
  (The planning issue was never created; Step 1 was skipped.)

gh pr list access confirmed.
