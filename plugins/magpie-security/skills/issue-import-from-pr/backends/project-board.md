<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr — the project board

## Step 5d — the target column

Target column: `Assessed`.
Its option ID comes from [`<project-config>/project.md`](../../../../../<project-config>/project.md#github-project-board);
re-fetch it via the introspection query in [`tools/github/project-board.md`](../../../../../tools/github/project-board.md) if a write returns `not found`.
When `tracker.project_board_enabled` is `false`, skip this step.

This follows the *Label + body state → Status* mapping: scope label applied, no CVE yet → `Assessed`.

## Step 7d — pin the new issue

Run the orphan-issue path from
[`tools/github/project-board.md`](../../../../../tools/github/project-board.md#orphan-issue-path)
with the new issue's `node_id`, then set `Status` to `Assessed` with its write recipe.
The *Auto-add to project* workflow may already have added the issue; `addProjectV2ItemById` is idempotent, so both cases converge.
The `pid` / `fid` / `oid` values come from [`project.md`](../../../../../<project-config>/project.md#github-project-board);
re-fetch them via the introspection query if either mutation returns `not found`.
