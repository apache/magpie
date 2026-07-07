<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare 0.9.3
Project: Velox Stream (non-ASF, github-releases backend)

release-management-config.md:
  release_branch_base: main
  release_dist_backend: github-releases
  release_approval_mechanism: pr-approval
  release_announce_backend: github-release-notes
  approval_pr_branch_pattern: release/<version>
  approval_pr_min_approvals: 2
  release_approver_roster_path: release-trains.md
  version_manifest_files: pyproject.toml
  category_x_dependencies: (empty)
  release_planning_issue_template: (not set; use default)

release-trains.md contains entry for 0.x train, version 0.9.3,
  Release Manager: @alex-velox, base branch: main.

gh pr list access confirmed: velox-community/velox-stream responds with merged PRs.
Previous release tag detected: 0.9.2

No .apache-magpie.local.lock drift.
No .apache-magpie-overrides/release-prepare.md found.
