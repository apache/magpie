<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `first_time_stale_abandoned` — row 0

**Fires when** a first-time contributor's PR carries a triage marker (comment or fold) with no push since, and the last commit is at least 30 days old.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it. The action is `skip`; this file only explains the skip if the maintainer asks.

Row 0 is evaluated **before** row 1 on purpose.
Without it, an abandoned first-time PR that has sat for months since being triaged keeps surfacing in the `approve-workflow` group every sweep, where the maintainer either re-approves CI on dead code or has to skip it manually.
The [stale-sweep flow](sweep-1b-stale-untriaged-draft.md) is the right place to retire the PR; the classifier's job here is just to keep it out of the workflow-approval group.

The 30-day threshold is intentionally longer than the grace periods (24h / 96h) and the F5a cooldown (72h).
It captures *abandonment*, not slow response — a contributor who replies within a week and then stalls for another week is not abandoned, just busy.
