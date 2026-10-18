<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `deterministic_flag` → `ping` — row 15

**Fires when** unresolved collaborator threads are the only signal, CI is green, and the author has not engaged with every thread.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; `details.reviewers` names the thread openers.

**Proposed action:** `ping` — [`actions/ping.md`](../actions/ping.md). The note nudges the author; reviewers are named backtick-quoted, never `@`-mentioned.

## Why

The threads are open and the author has not engaged in a way the heuristic recognises.
The safe default is to nudge the author without claiming anything about resolution.
`ping` is the lightest touch: right when the contributor is still iterating and dropping back to draft would be discourteous.

Contributor-opened threads do not count — the qualifier is the thread's first comment by a collaborator.
