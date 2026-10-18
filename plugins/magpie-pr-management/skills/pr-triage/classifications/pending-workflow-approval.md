<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `pending_workflow_approval` — row 1

**Fires when** the head SHA has workflow runs awaiting approval (the `action_required` index), or a first-time contributor's rollup shows no real CI ran.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; the group's `details.runs` lists the pending runs it found.

**Proposed action:** `approve-workflow` — [`actions/approve-workflow.md`](../actions/approve-workflow.md).
This group skips the generic group menu: walk it with the list-then-select flow in [`workflow-approval.md`](../workflow-approval.md).

## What you judge

Read the diff before anything runs. Approving a workflow lets a first-time contributor's code run inside the project's CI with its secret material — the single most sensitive decision in this skill.
The inspection protocol and what counts as suspicious are in [`workflow-approval.md`](../workflow-approval.md); a suspicious diff goes to [`flag-suspicious`](../actions/approve-workflow.md#flag-suspicious--close-all-open-prs-by-the-author), never to approval.

## Why

The REST `action_required` index is the **primary** signal, not a fallback.
Empirically (2026-04, `<upstream>`), 17 first-time-contributor PRs in a single sweep reported `statusCheckRollup.state == SUCCESS` while every real CI workflow was held in `action_required`.
Trusting the rollup classified all 17 as `passing` and would have applied `mark-ready` to PRs whose real CI never ran.
Golden rule 1b in [`SKILL.md`](../SKILL.md) captures this as a mandatory invariant.
