<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Batch failure budget](#batch-failure-budget)
  - [Two phases, two rules](#two-phases-two-rules)
  - [What counts as an item failure](#what-counts-as-an-item-failure)
  - [The budget](#the-budget)
  - [The recap](#the-recap)
  - [Where it is implemented](#where-it-is-implemented)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Batch failure budget

The contract every batch (sweep) skill follows when one item of its pool
cannot be processed. Spec:
[`batch-failure-budget.md`](../tools/spec-loop/specs/batch-failure-budget.md).

## Two phases, two rules

A sweep reads and classifies a pool of items, then writes (posts, labels,
closes) the ones the maintainer confirmed.

- **Read and classify: budgeted.** One item whose own data makes the step
  impossible is recorded as `failed` with its reason and skipped; the sweep
  carries on. Only when more items fail than the budget allows does the sweep
  stop, before the next item.
- **Write: never budgeted.** A failed write stops the run at once and is not
  retried, because a retry can post the same comment or label twice. The
  recap names the failed item and the selector that resumes from the next one.

## What counts as an item failure

The item's own data made the step impossible: its body is missing, a
timestamp will not parse, the item returns 404 or 410, its saved read is
malformed, or the classifier returned no verdict for it twice. A failure that
is about the connection rather than the item (a rate limit, a 5xx, an expired
token) is a harness failure; it is handled by the harness-outage exclusion,
which builds on this budget and is specified separately.

## The budget

`item_failure_budget`, in the config file the skill already reads
(`issue-tracker-config.md` for the issue skills, `project.md` for the security
skills, `pr-management-config.md` for the PR skills):

| Value | Means |
|---|---|
| `<n>` | tolerate `n` item failures |
| `<p>%` | tolerate `p` percent of the pool, rounded down |
| `max(<n>, <p>%)` | whichever is larger |

Unset means `max(3, 10%)`. A malformed value stops the run before the sweep
starts, with an error naming the value; it never falls back to the default
silently. Nothing has been read at that point, so the recap lists no failed
or unfinished items: fix the value and rerun the same selector.

## The recap

Three groups, always in this order: **completed**, with their dispositions;
**failed**, each with its reason; **unfinished**, the items not reached, with
the reason stated once (budget exhausted, or a write stopped the run). Then
the selector that reruns exactly the failed and unfinished items. A sweep
with no failures does not mention the budget at all.

## Where it is implemented

- The prose rule is the shared block `tools/dev/blocks/item-failure-budget.md`,
  propagated into `issue-triage`, `security-issue-triage`, `issue-stale-sweep`,
  `pr-stale-sweep`, `issue-reassess` and `good-first-issue-sweep`.
- `pr-stale-sweep`'s sweep is deterministic code, so the budget is code there:
  `tools/pr-management/src/pr_management/failure_budget.py`, used by
  `pr-management stale-sweep classify`, which reports `failed`, `budget`,
  `unfinished`, `stopped` and `rerun_selector`.
