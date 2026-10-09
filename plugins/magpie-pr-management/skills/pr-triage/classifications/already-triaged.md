<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `already_triaged` — rows 3 and 4

**Fires when** a triage marker newer than the last commit is under 7 days old: a triager's comment carrying the `Pull Request quality criteria` link text, or the PR body's `pr-triage-fold` block with a matching `head=`.
Row 3 is sub-state `waiting` (no author activity since), row 4 is `responded`.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it. The action is `skip`; this file only explains the skip if the maintainer asks.

Two sub-states matter:

- **waiting** — no author comment after the triage comment. Quiet `skip`; nothing to do.
- **responded** — author commented, possibly with a question that needs a maintainer answer. Quiet `skip` here too; we do not auto-suggest a reply because the author's response might not be a fix push.

The 7-day cutoff into `stale_draft` ([row 5](stale-draft.md)) is what stops forever-waiting PRs from sitting in the queue.

Marker detection is **triager-scoped, not viewer-scoped**.
With several committers triaging the same queue, a marker left by another triager must suppress the duplicate proposal exactly like the viewer's own — the wasted-attention and duplicate-comment harm this row exists to prevent does not care who triaged.
On the comment channel the gate is the author association (`OWNER` / `MEMBER` / `COLLABORATOR`), which is the same gate `pr-management-stats` applies, so the two skills agree on what a triage marker is.
On the fold channel the block is a single managed span on the PR body — inherently shared across triagers — and carries the writer's login in `by=`, which the reason names so the maintainer can see *who* to sync with before re-engaging.

The marker text is load-bearing: it must appear verbatim in every triage body, which the renderer guarantees.
A folded confirmation request (`action=request-author-confirmation`) is not a triage marker for these rows; rows [14a](author-confirmed-ready.md) / [14b](awaiting-author-confirmation.md) own it.
