<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `stale_draft` → `close-stale` — Sweep 1a, triaged draft

**Fires when** a draft without the ready label carries a triage marker at least `stale_draft_triaged_days` (default 7) old, and the author has neither commented nor pushed since.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it.

**Proposed action:** `close-stale` — [`actions/close-stale.md`](../actions/close-stale.md), the stale-draft notice, no label.
Batchable, but with a per-PR confirm inside the batch.

## Why a push counts as a response

Many contributors answer review feedback with code and never write a comment.
Testing this trigger against comments only marks those authors silent while they are actively working — and the action is a close, the least reversible thing the skill does.
On a full sweep of a large `<upstream>`, one of three PRs a comments-only reading would have closed had author pushes 5, 12 and 25 days after the triage comment.

A marker left by another triager feeds this close only once that triager passes the live maintainer check.

Every sweep honours two guards the classifier applies before it proposes anything:

- **Maintainer court.** A PR whose author asked a maintainer a question no maintainer has answered is waiting on *us*; Sweeps 1–3 skip it and Sweep 4 keeps its label. Inactivity timers do not override this — only a maintainer reply does. This is the failure that closed a real PR while an open question to the team sat unanswered.
- **Ready-label exclusion.** A PR carrying `ready for maintainer review` belongs to [Sweep 4](sweep-4-stale-ready-label.md) alone; Sweeps 1–3 never close it, draft it, assign its author or fold a note into it. Re-confirm the label is still absent immediately before a Sweep 1–3 mutation — it may have been added since the sweep.
