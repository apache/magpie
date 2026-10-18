<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `strip-ready-label` — hand an author-court PR back

Used by [Sweep 4](../classifications/sweep-4-stale-ready-label.md) only, when the next move to make the PR mergeable is the author's.
A maintainer-court PR is never passed here.

The strip and its author-facing action are one unit of work, in this pass, and the strip is never silent:

1. **Deliver the note and audit marker** — [`deliver-note.md`](deliver-note.md), action `strip-ready-label`, with the group entry's `details` (`author_action`, `audit_marker`, `fold_into_audit`).
   When the author-facing action is itself a note (`ping`, `request-author-confirmation`), it is folded into the same body; a quality-flag `comment` or `draft` keeps its own body, and the audit marker accompanies it.
2. **Remove the label** — after the note, never before:

   ```bash
   gh pr edit <N> --repo <upstream> --remove-label "ready for maintainer review"
   ```

Failure handling: a 422 "label does not exist" is benign (the end state is already in place); a 404 or network error is surfaced with the PR number, not retried; anything else stops the batch.
