<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #3004
Author: github-actions
IsDraft: true
Base: v3-3-test
Title: [v3-3-test] Stop shipping broken agent-skill symlinks in the source release (#2107)
Commits:
  feff8cff16 [v3-3-test] Stop shipping broken agent-skill symlinks in the source release (#2107)
  a84a76d9a1 [v3-3-test] Keep the Gradle wrapper jar out of the source release (#2108)
SourceCommits:
  feff8cff16 -> 4b0eb8e020 (on default branch)
  a84a76d9a1 -> 1f0e2d3c4b (on default branch)
GitCherry:
  - feff8cff16
  - a84a76d9a1
PatchIdU0Match:
  (no remaining commits)
SourcePR:
  Title: Stop shipping broken agent-skill symlinks in the source release
  Labels: [area:dev-tools, backport-to-v3-3-test]
  Description: The source release contained dangling symlinks.
  Files: .gitattributes
