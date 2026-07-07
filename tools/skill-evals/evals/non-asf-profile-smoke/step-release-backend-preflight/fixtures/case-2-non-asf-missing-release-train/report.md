<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare 1.0.0
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

release-trains.md: Contains only a 0.x train entry. No entry exists
  for version 1.0.0 or any 1.x train.

gh pr list access confirmed: velox-community/velox-stream responds.
