<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `awaiting_author_confirmation` — row 14b

**Fires when** we asked the author to confirm readiness after the head commit and the author has not replied yet.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it. The action is `skip`; the PR forms no group.

Posting a second request inside the cooldown would be the bot nagging.
The author has the question; the silence is informative.
[Sweep 5](sweep-5-stale-confirmation-request.md) escalates deterministically once the cooldown has elapsed, and a fresh push invalidates the request (new code, possibly new threads) so the PR re-classifies against the new state.
