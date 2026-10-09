<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `stale_author_confirm_request` → `ping` — Sweep 5

**Fires when** we asked the author to confirm readiness, the head has not moved, the author has not replied, and the request is at least 7 days old.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it.

**Proposed action:** `ping` — [`actions/ping.md`](../actions/ping.md), the unresolved-thread nudge to the author. Simple `[A]ll`: a single non-destructive note.

## Why not `close` or `draft`

`close` would punish a contributor whose only fault is missing a confirmation question; `draft` would lose the review-ready posture though every other signal is healthy.
The confirmation request was a softer ask that did not land; the ping makes the unresolved threads the topic again.

## Override

If the threads are obviously addressed (the author engaged substantively in-thread but never answered the confirmation), override the group to `mark-ready`.
It is not the default because a programmatic test for "substantive engagement" would bring back the false positives the two-sweep gate removed.
