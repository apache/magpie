<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `stale_workflow_approval` → `draft` — Sweep 3

**Fires when** a PR awaiting workflow approval, without the ready label, has had no activity for `stale_workflow_approval_days` (default 28) and no push since.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it.

**Proposed action:** `draft` — [`actions/draft.md`](../actions/draft.md), with the stale-workflow-approval note, no label. Simple `[A]ll`.

## Why

A first-time contributor's PR waiting a month for approval usually means the attempt was abandoned.
Closing feels harsh when they never even got CI feedback; drafting clears the queue and leaves them the option to resume.

Every sweep honours two guards the classifier applies before it proposes anything:

- **Maintainer court.** A PR whose author asked a maintainer a question no maintainer has answered is waiting on *us*; Sweeps 1–3 skip it and Sweep 4 keeps its label. Inactivity timers do not override this — only a maintainer reply does. This is the failure that closed a real PR while an open question to the team sat unanswered.
- **Ready-label exclusion.** A PR carrying `ready for maintainer review` belongs to [Sweep 4](sweep-4-stale-ready-label.md) alone; Sweeps 1–3 never close it, draft it, assign its author or fold a note into it. Re-confirm the label is still absent immediately before a Sweep 1–3 mutation — it may have been added since the sweep.
