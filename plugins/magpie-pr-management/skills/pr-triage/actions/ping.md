<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `ping` — nudge the author about review feedback

Deliver the note — [`deliver-note.md`](deliver-note.md), action `ping`.
The renderer picks the body from the row: the review nudge for [`stale_review`](../classifications/stale-review.md), the thread nudge for [unresolved threads](../classifications/unresolved-threads.md).

The note goes to the author, and only the author: reviewers are named backtick-quoted (`` `@login` ``), never `@`-mentioned, and the author pings them from their own account once the feedback is addressed.
The reviewer-re-review and reviewer-ping variants that summoned a maintainer are gone.

`ping` does not strip the ready label: it treats the regression as transient.
