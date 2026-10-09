<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `stale_draft` — row 5

**Fires when** a current triage marker is at least 7 days old, the author has not responded, and the PR is a draft.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it and defers the PR to [Sweep 1a](sweep-1a-stale-triaged-draft.md); the table itself proposes nothing.

After 7 days with no author reply on a draft, the close-with-stale-notice sweep takes over — that is what stops forever-waiting PRs from sitting in the queue.
