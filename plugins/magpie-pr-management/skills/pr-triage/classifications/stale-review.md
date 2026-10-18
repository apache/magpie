<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `stale_review` → `ping` — row 18

**Fires when** a reviewer requested changes, the author pushed afterwards (more than 24 hours ago), and neither side followed up: no author comment naming the reviewer since the review, no reviewer comment since the push.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; `details.reviewers` names them.

**Proposed action:** `ping` — [`actions/ping.md`](../actions/ping.md), the review-nudge note to the author.

## Why

The author is ostensibly waiting on a re-review but never nudged.
The note goes to the author, naming the reviewer backtick-quoted; the author pings the reviewer from their own account when ready.
A push less than 24 hours old is itself the follow-up — the author is still working through the feedback.
