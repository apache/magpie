<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #3001
Author: github-actions
IsDraft: true
Base: v3-3-test
Title: [v3-3-test] UI: Fix copied SQL from Rendered Templates breaking at every token (#2633)
Commits:
  a46889de44 [v3-3-test] UI: Fix copied SQL from Rendered Templates breaking at every token (#2633)
SourceCommits:
  a46889de44 -> ffa19c31a6 (on default branch)
GitCherry:
  + a46889de44
PatchIdU0Match:
  a46889de44: yes
SourcePR:
  Title: UI: Fix copied SQL from Rendered Templates breaking at every token
  Labels: [area:UI, backport-to-v3-3-test]
  Description: Copying SQL from the Rendered Templates view inserted a line break after every token, so the pasted query did not run.
  Files: ui/src/components/RenderedSql.tsx, ui/src/components/RenderedSql.test.tsx
