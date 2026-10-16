<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Receipt draft — `Report (disposition converged)`

`ack-decision` printed `draft_created: false` and a `rollup_receipt` with `converged: true`.

From the [Step 3 classification table](../SKILL.md#step-3--classify-each-candidate):
Proceed to Step 4 (extract template fields and create the tracker for audit trail); in Step 7, **skip the canned receipt-of-confirmation reply** (the reporter has already seen our substantive response and a canned receipt would be tone-deaf). Note in the rollup entry that the disposition is converged on the inbound thread.

From Step 7 item 4:

- The candidate class is `Report (disposition converged)` — skip the draft entirely;
  note the converged disposition in the rollup entry (step 5 below)
  with the exact prior thread URL / message-id where it was reached.
  Do not create a Gmail draft for this tracker.

Pass that URL or message-id as `converged_ref`; `render-rollup` writes it into the receipt line.
