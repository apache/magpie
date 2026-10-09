<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `stale_ready_label` → `strip-ready-label` — Sweep 4

**Fires when** a PR has carried the ready label for at least 7 days, has been quiet for 7 days (no commit, comment or review by anyone), and its live re-classification says the next move is the **author's**: a conflict to rebase, an author-caused CI or static failure, unresolved threads the author has not engaged, or readiness to confirm.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it from the live mergeability read (`gql-pr-liveness`, requested under `needs`); `details` names the author-court trigger and the author-facing action that goes with the strip.

**Proposed action:** `strip-ready-label` — [`actions/strip-ready-label.md`](../actions/strip-ready-label.md): the author-facing note and the audit marker, then the label comes off, in one pass. One `[A]ll`-confirmable group.

A candidate whose next move is a **maintainer's** keeps the label: it is exactly where it belongs.
When that move does something (approve a workflow, rerun flaky CI, update a branch), the PR joins that action's normal group instead.
Unknown mergeability after the live read defers the PR to the next sweep.

## Why court, not staleness

`ready for maintainer review` means **the ball is in the maintainers' court**.
This sweep once read staleness as guilt: a healthy stale PR was stripped, a rotted one closed.
That is backwards — a healthy, author-silent ready PR, especially one a committer has approved and that is mergeable, is waiting on *us*; stripping its label de-queues a PR that is ready to land.
A rotted branch is the author's to rebase; jumping to `close` throws away recoverable work, so this sweep hands rotted branches back and never closes — [Sweep 2](sweep-2-inactive-open.md) retires them if they stay abandoned.

Two failures this fixes, both seen in the wild:

1. **`COLLABORATOR` ≠ committer.** A read-only router's comment once satisfied an "author silent after a maintainer comment" trigger and an approved, mergeable PR was stripped. Maintainer status is now committer-team membership or `write`+ permission.
2. **Silent strips.** Removing a public label with no comment reads as an unexplained yank — a stripped PR once drew a public "why was this removed?" with no trace to answer it. Every strip carries the audit marker.

The batch's mergeability is unreliable on the ready queue: GitHub computes it lazily, and branch protection reports most of it `BLOCKED` pending approval.
A batch mergeability gate misjudged ~87% of a real ready queue, which is why the live read is mandatory here.

The reason string must name the author-court trigger ("merge conflict — author must rebase"), never a bare "ready label stale".
