<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `request-author-confirmation` — ask the author whether the feedback is addressed

Deliver the note — [`deliver-note.md`](deliver-note.md), action `request-author-confirmation`.
The renderer picks the `confirmation_handback_mode` variant and keeps the marker `ready for maintainer review confirmation` verbatim: it is what the next sweep looks for.

No label, no reviewer mention — that is the second leg, gated on the author's reply ([row 14a](../classifications/author-confirmed-ready.md)).

What happens next:

- Author replies → the next sweep proposes `mark-ready`, with the reply shown for the maintainer to read.
- Author silent → [Sweep 5](../classifications/sweep-5-stale-confirmation-request.md) escalates after the cooldown.
- Author pushes first → the request predates the new head and the PR re-classifies.

A failed delivery is non-destructive: surface it and retry next sweep.
If a drill-in shows the threads are not actually addressed, override to [`ping`](ping.md).
