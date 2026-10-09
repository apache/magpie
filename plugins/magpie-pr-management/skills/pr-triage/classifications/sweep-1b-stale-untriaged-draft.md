<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `stale_draft` → `close-stale` — Sweep 1b, untriaged draft

**Fires when** a draft without the ready label and with no triage marker has had no activity for `stale_draft_untriaged_days` (default 14).
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it, after Sweep 1a so the more precise trigger wins.

**Proposed action:** `close-stale` — [`actions/close-stale.md`](../actions/close-stale.md), the untriaged-draft variant of the notice, no label.
Batchable, with a per-PR confirm inside the batch.

Every sweep honours two guards the classifier applies before it proposes anything:

- **Maintainer court.** A PR whose author asked a maintainer a question no maintainer has answered is waiting on *us*; Sweeps 1–3 skip it and Sweep 4 keeps its label. Inactivity timers do not override this — only a maintainer reply does. This is the failure that closed a real PR while an open question to the team sat unanswered.
- **Ready-label exclusion.** A PR carrying `ready for maintainer review` belongs to [Sweep 4](sweep-4-stale-ready-label.md) alone; Sweeps 1–3 never close it, draft it, assign its author or fold a note into it. Re-confirm the label is still absent immediately before a Sweep 1–3 mutation — it may have been added since the sweep.
