<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `stale_copilot_review` — row 2

**Fires when** an unresolved review thread opened by a Copilot reviewer is at least `stale_copilot_days` (default 7) old and the author has not replied in the thread or on the PR since.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; `details.copilot_thread` is the thread URL the violation must cite.

**Proposed action:** `draft` — [`actions/draft.md`](../actions/draft.md), with the "Unaddressed Copilot review" violation pointing at that thread.

## Why

Copilot-review comments are work items queued against the author.
Even when individual Copilot suggestions turn out to be wrong, the author is still responsible for replying — accept, reject with a one-line explanation, or fix.
When Copilot comments sit unresolved for a week the PR has stalled — author is either unaware of the feedback or assuming someone else will triage it.

`draft` is the softer equivalent of the stale-draft sweep: it unblocks the maintainer review queue while preserving the conversation for when the author returns.

Why 7 days, not 24h / 96h:

- Review feedback takes longer to address than a CI-flake nudge.
- A same-week nudge would be noisy.
- The threshold matches the patience budget for any unresolved reviewer thread, just with the Copilot-specific message body.

Why row 2 and not later: Copilot signal is more specific than the generic `unresolved review thread` row.
A PR with both signals should get the Copilot-specific message because it points the author at the actual unresolved thread URL — listing both violations in one comment is fine, but the action and template are picked from row 2.

The Copilot login match is a substring match without requiring `[bot]`: GitHub's GraphQL `Actor.login` returns some Copilot integrations (e.g. `copilot-pull-request-reviewer`) without the suffix the REST API shows.
