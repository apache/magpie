<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `draft` — convert to draft and deliver the violations

Sequence matters: convert first, then deliver the note.
Delivering before converting risks a "converted to draft" note on a still-open PR if the conversion fails.

1. **Ready label, when `details.strip_ready_label` is set** — remove it first, so the queue position is corrected even if a later step fails:

   ```bash
   gh pr edit <N> --repo <upstream> --remove-label "ready for maintainer review"
   ```

   A 422 "label does not exist" is benign; log and continue.
   Any other failure: surface it and proceed — the draft and the note still land, and the preview already told the maintainer the strip would run.
2. **Convert** — skip when the PR is already a draft, or the author is a collaborator (never draft a collaborator's PR; the classifier already turns that into `comment`):

   ```bash
   gh pr ready <N> --repo <upstream> --undo
   ```

   On failure: surface the error and **do not** deliver the note.
3. **Deliver the note** — [`deliver-note.md`](deliver-note.md), action `draft`.
   On failure after a successful conversion: surface it and leave the PR a draft; the next sweep re-delivers. Do not roll back the draft.

The merit-discussion exception never reaches this file: a ready PR with a maintainer review thread in flight arrives as [`comment`](comment.md) with `details.degraded_from: draft`.
