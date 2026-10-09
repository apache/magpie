<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `deterministic_flag` → `draft` — row 17, fallback

**Fires when** a deterministic signal is present (conflict, CI failure past its grace window, or an unresolved collaborator thread) and no earlier row matched.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it, with the ready-label rules applied.

**Proposed action:** `draft` with the violations — [`actions/draft.md`](../actions/draft.md).

## Why

The catch-all that prevents a "no proposal" outcome on a flagged PR.
Deliberately conservative — better to nudge the author too gently than to miss queue pressure.
`draft` flips the PR out of the review queue: "stop requesting review, fix these first, mark ready yourself".
