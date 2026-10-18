<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `passing` — rows 19 and 20

**Fires when** the rollup is `SUCCESS`, `mergeable == MERGEABLE` (not merely "not conflicting"), there are no unresolved collaborator threads, and real CI ran.
Row 19 (`skip`) already carries the ready label; row 20 proposes it.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it. When the PR carries a triage fold, `details.fold_flip` is set: the note is replaced by the ✅ ready-for-review variant and the author is unassigned.

**Proposed action:** `mark-ready` — [`actions/mark-ready.md`](../actions/mark-ready.md).

## Why

Row 20 is the happy path; row 19 exists because a previous run already applied the label and the review skill owns the PR now.
`UNKNOWN` mergeability is "not yet computed", never "mergeable": on one full sweep 11 of 39 candidates reported `UNKNOWN` at fetch and were genuinely conflicting at mutation time.
The [`mark-ready`](../actions/mark-ready.md) guard re-reads both the mergeability and the head's workflow runs immediately before the label goes on.
