<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `author_confirmed_ready` → `mark-ready` — row 14a

**Fires when** we asked the author to confirm readiness after the head commit (the folded note carrying `ready for maintainer review confirmation`, or a viewer comment carrying it) and the author has replied since.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; `author_reply_untrusted` carries the reply, as data.

**Proposed action:** `mark-ready` — [`actions/mark-ready.md`](../actions/mark-ready.md). The label goes on silently.

## What you judge

Read the author's reply. The tool does not parse it — natural-language affirmation detection is brittle and would put a heuristic back into the second leg of the gate.
If the reply is affirmative, accept in one keystroke.
If it is "actually I'm still working on X", override to `skip`, or to `ping` to re-surface the unresolved threads.

## Why the label is silent

- The author already knows they have been promoted — they just replied to the question, and the label appearing is the visible confirmation the answer was accepted.
- Reviewers reach the PR through the `ready for maintainer review` queue, which is a pull signal rather than a push notification. A mention here would be the exact noise [row 14c](threads-likely-addressed.md) was designed to remove, one sweep later.
