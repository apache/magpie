<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — pin to the `Needs triage` column

From Step 5c.

Run the orphan-issue path from
[`tools/github/project-board.md`](../../../../../tools/github/project-board.md#orphan-issue-path)
with the new issue's `node_id`, then set `Status` to `Needs triage`
with its write recipe. The `pid` / `fid` / `oid` values come from
[`<project-config>/project.md`](../../../../../<project-config>/project.md#github-project-board);
re-fetch them via the introspection query in
[`project-board.md`](../../../../../tools/github/project-board.md) if
either mutation returns `not found`.
