<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare 2.11.0

release-management-config.md:
  release_branch_base: main
  version_manifest_files: setup.cfg, airflow/__init__.py
  category_x_dependencies: (empty)
  release_planning_issue_template: (not set; use default)

release-trains.md contains entry for 2.x train, version 2.11.0,
  Release Manager: @jmclean, base branch: main.

gh pr list access confirmed: apache/airflow responds with merged PRs.
Previous release tag detected: 2.10.3

.apache-magpie.local.lock matches .apache-magpie.lock — no drift.
No .apache-magpie-overrides/release-prepare.md found.
