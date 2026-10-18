<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `inactive_open` → `draft` — Sweep 2

**Fires when** a non-draft PR without the ready label has had no activity for `inactive_open_days` (default 28) and no other stale classification applies.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it.

**Proposed action:** `draft` — [`actions/draft.md`](../actions/draft.md), with the inactive-to-draft note, no label. Simple `[A]ll`: the author can revert with one click.

## Why draft, not close

Closing an inactive *open* PR is more disruptive than closing a draft — the author actively asked for review at some point.
Converting to draft stops it blocking the queue, preserves the discussion, and the author can mark it ready again when they resume.
This sweep is also what eventually retires a PR [Sweep 4](sweep-4-stale-ready-label.md) handed back.

Every sweep honours two guards the classifier applies before it proposes anything:

- **Maintainer court.** A PR whose author asked a maintainer a question no maintainer has answered is waiting on *us*; Sweeps 1–3 skip it and Sweep 4 keeps its label. Inactivity timers do not override this — only a maintainer reply does. This is the failure that closed a real PR while an open question to the team sat unanswered.
- **Ready-label exclusion.** A PR carrying `ready for maintainer review` belongs to [Sweep 4](sweep-4-stale-ready-label.md) alone; Sweeps 1–3 never close it, draft it, assign its author or fold a note into it. Re-confirm the label is still absent immediately before a Sweep 1–3 mutation — it may have been added since the sweep.
