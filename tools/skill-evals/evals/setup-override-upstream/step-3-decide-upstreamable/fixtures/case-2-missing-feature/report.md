<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Override file: `.apache-magpie-overrides/pr-management-triage.md`
Override content summary:
  # Override 1 — Skip draft PRs
  Before any classification work, check whether the PR is in draft
  state (GitHub `draft: true`). If it is, skip triage entirely and
  leave a comment: "PR is in draft — triage will run once it is
  marked ready for review." This avoids labelling and routing PRs
  that the author is not finished writing.

Framework skill: `pr-management-triage`
Relevant section: "Step 1 — Classify"
The framework currently classifies all PRs regardless of draft state.
The override adds a short-circuit gate that other adopters would
also benefit from.
