<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `deterministic_flag` → `request-author-confirmation` — row 14c

**Fires when** unresolved collaborator threads are the only signal, CI is green, and every thread shows author engagement: the latest commit post-dates the newest thread, and each thread has an in-thread author reply or a commit after it.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; `details.reviewers` names the thread openers.

**Proposed action:** `request-author-confirmation` — [`actions/request-author-confirmation.md`](../actions/request-author-confirmation.md).
No label, no reviewer mention: the note asks the author, and only the author.

## Why a two-sweep gate

The engagement heuristic is an *engagement* signal, not a *resolution* signal:

- A post-review commit does not guarantee the commit addresses the specific thread (it can touch unrelated files, fix only one of several open threads, or be a follow-up to a different review).
- An in-thread author reply does not guarantee the reply resolves the thread (it can be a clarifying question, a partial fix, or pushback on the reviewer's framing).

An earlier single-sweep `mark-ready-with-ping` collapsed heuristic match → label + reviewer mention into one step and asserted the threads "appear to have been addressed" — a stronger claim than the evidence supported.
False positives landed on the original reviewers as notifications and asked them to do the verification work the heuristic could not.

The gate moves the verification to the only party who reliably knows whether the feedback is addressed: the author.
The trade-off is one sweep of latency for removing the reviewer-mention path entirely.
Promoting the PR here would re-introduce the single-sweep failure; the label is gated on the author's own statement ([row 14a](author-confirmed-ready.md)).

The heuristic stays conservative on purpose: tightening it further (per-thread commit attribution) gains little once the gate filters the false positives.
