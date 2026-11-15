<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR: #2110 "docs(setup): clarify the snapshot drift message"
mergeStateStatus: BLOCKED
autoMergeRequest: enabled
Files changed: docs/setup/agentic-overrides.md

Checks:
  prek            fail  6m02s

prek job log (tail):
  ruff check (workspace)........Failed
  SIM102 Use a single `if` statement instead of nested `if` statements
    --> src/pr_management/triage/recovery.py:528:9
  SIM102 Use a single `if` statement instead of nested `if` statements
    --> src/magpie_sourcehut/cli.py:236:9
  markdownlint..................Passed

<default-branch> latest whole-tree run: failure, same two SIM102 findings, after "chore(deps): bump ruff 0.17.3 -> 0.17.4" merged.

Inline review comments: none
