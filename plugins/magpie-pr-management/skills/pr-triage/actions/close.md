<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `close` — close with the reasoning and the quality-violations label

Always per PR, never batched — even inside a `close` group the maintainer confirms each one.
Deliver the reasoning **first**, so the description already explains the close when the close notification fires.

1. **Deliver the note** — [`deliver-note.md`](deliver-note.md), action `close`.
2. **Close** — skip when `details.skip_close` is set (a maintainer review discussion is in flight on a ready PR; the PR stays open with both labels for a human to decide, and the preview must say so):

   ```bash
   gh pr close <N> --repo <upstream>
   ```

3. **Label** — when `quality_violations_close` is configured and the label exists on the repo:

   ```bash
   gh pr edit <N> --repo <upstream> --add-label "closed because of multiple quality violations"
   ```

   A missing label is a one-line warning, not a failure.

When `details.strip_ready_label` is set and the PR is being closed, remove the ready label after the note as in [`draft.md`](draft.md) step 1.
