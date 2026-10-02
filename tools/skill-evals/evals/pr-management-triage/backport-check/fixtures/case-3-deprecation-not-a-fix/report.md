<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #3003
Author: github-actions
IsDraft: true
Base: v3-3-test
Title: [v3-3-test] Add type-checking guards to DeadlineAlert init (#2294)
Commits:
  65b19a6b45 [v3-3-test] Add type-checking guards to DeadlineAlert init (#2294)
SourceCommits:
  65b19a6b45 -> b9e46d64ee (on default branch)
GitCherry:
  + 65b19a6b45
PatchIdU0Match:
  65b19a6b45: yes
SourcePR:
  Title: Add type-checking guards to DeadlineAlert init
  Labels: [area:deadline-alerts, area:task-sdk, backport-to-v3-3-test]
  Description: DeadlineAlert now refuses a callback that is not exactly AsyncCallback or SyncCallback, so a subclass fails at Dag parse time. Passing a number as the interval is deprecated and now emits RemovedInAirflow4Warning.
  Files: newsfragments/2294.significant.rst, sdk/definitions/deadline.py, sdk/definitions/callback.py, tests/test_deadline.py
