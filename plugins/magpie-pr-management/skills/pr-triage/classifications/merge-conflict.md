<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `deterministic_flag` → `draft` — row 9, merge conflict

**Fires when** `mergeable == CONFLICTING`.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it, with the ready-label rules applied (`details.strip_ready_label`, `details.merit_discussion`, `details.degraded_from`).

**Proposed action:** `draft` with the merge-conflicts violation — [`actions/draft.md`](../actions/draft.md).
When a merit discussion keeps a ready label on, the action arrives as `comment` (`details.degraded_from: draft`): [`actions/comment.md`](../actions/comment.md).

## Why `CONFLICTING` always means draft, never rebase

GitHub's `update-branch` endpoint side-merges `<base>` into the PR head and refuses on conflicts.
Empirically every rebase attempt on a `CONFLICTING` PR has returned "Cannot update PR branch due to conflicts" and wasted a round-trip.
Routing straight to `draft` with the merge-conflicts violation points the author at the local-rebase instructions in their note.
