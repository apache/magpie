<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `deterministic_flag` → `close` — row 8

**Fires when** the same author has more than 3 PRs with a deterministic signal in this sweep, and this PR has one too.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it and applied the ready-label rules: `details.strip_ready_label`, `details.merit_discussion`, `details.skip_close`.

**Proposed action:** `close` — [`actions/close.md`](../actions/close.md). Always per PR, never batched.

## Why

Queue pressure from a single contributor with many low-quality PRs is a different signal than a single broken PR — the proportionate response is "talk to them, close the bulk", not "draft them all and triple the comment volume".

The count is over the PRs this sweep fetched, after the pre-filters, so a narrowed selector (`author:`, `label:`) counts only what it fetched.

## What you judge

A wrongly-closed PR is the hardest mistake to recover from: read each one.
When `details.skip_close` is set, a maintainer review discussion is in flight on a ready-for-review PR — the close reasoning and the quality label still go on, the PR stays open (the merit-discussion exception).
