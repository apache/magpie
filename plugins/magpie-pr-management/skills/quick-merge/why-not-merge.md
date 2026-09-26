<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Why the skill does not merge (Agentic Autonomous)

The framework's [`docs/labels-and-capabilities.md`](../../../../docs/labels-and-capabilities.md)
defines `mode:Autonomous` as *"narrowly-scoped auto-merge (off until
Triage/Mentoring/Drafting run 2 quarters)"*. A per-PR-confirmed merge of a
trivial PR is precisely narrowly-scoped auto-merge — it is Agentic Autonomous,
not a loophole around it. The framework chose to hold Agentic Autonomous back
until the Triage, Mentoring, and Drafting modes have demonstrated two quarters of
safe operation. This skill respects that decision: it ships the **Triage-mode
identification half** (sweep the queue, classify, propose for human action —
`capability:triage`) and stops at the boundary. The merge stays a manual
maintainer action.

When the governance gate lifts, a merge action belongs in a **separate,
explicitly Mode-D-labelled change** (its own skill or a gated sub-action) with
its own safety protocol — live gate re-verification immediately before merge,
head-SHA optimistic lock, branch-protection respect (no `--admin`, no force),
per-PR confirmation, never batch, and session-history logging. That change is
out of scope here and must not be smuggled in under `capability:triage`.
