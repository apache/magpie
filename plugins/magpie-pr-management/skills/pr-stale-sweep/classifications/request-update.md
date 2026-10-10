<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `REQUEST-UPDATE`

**Fires when** the PR has had no real activity for at least `warn_days` and carries no standing nudge (a nudge with no author activity since).
That includes a PR already idle past `close_days`: a PR is always nudged before it is closed, unless it is past the hard-close threshold.
[`stale-sweep classify`](../../../../../tools/pr-management/src/pr_management/stale_sweep/classify.py) decided it; the entry's `remaining_days` is what the nudge promises — `close_days` minus the days idle, and never less than 7, because no PR is closed less than a week after its nudge.

**Action:** post the rendered nudge (Step 6). No state change.

## What you judge

The greeting is rendered; nothing to word. If the maintainer knows the author is mid-work (a conversation elsewhere, a linked issue), drop the item.

## Why

A PR that never received a nudge must get one, and the warn-to-close window, before it can be closed: closing unwarned reads as the project discarding the contribution.
The nudge carries `<!-- pr-stale-sweep-nudge -->`, which is how a later sweep knows it was sent.
