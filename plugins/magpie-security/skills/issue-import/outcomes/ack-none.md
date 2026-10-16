<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Receipt draft — `reporter_acknowledgement_model: none`

`ack-decision` printed `draft_created: false` with `suppressed_reason` and `rollup_note`.

- `reporter_acknowledgement_model` is `none` (from the
  observed-state bag populated in Step 0, default `manual`) —
  skip the draft entirely. Record
  `acknowledgement_model=none: receipt-of-confirmation draft
  suppressed per <project-config>/security-intake-config.md
  disclosure_governance` in this tracker's rollup entry
  (Step 7.5 below). Surface a one-line note in the Step 8
  recap for each suppressed candidate.

Pass `rollup_receipt` to `render-rollup` (it carries the `suppressed_reason`) and `rollup_note` to the `render-recap` state's `notes`.
