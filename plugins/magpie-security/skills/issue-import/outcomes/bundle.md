<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Receipt draft — covered by a consolidated receipt

`ack-decision` printed `draft_created: false` and a `rollup_receipt` with the bundle's `bundle_draft_id`.

- The candidate is part of a **consolidated-receipt bundle**
  (Step 5's *"Consolidated receipts for multi-tracker imports"*) —
  the bundle, already confirmed at Step 5, covers it.
  Cross-link the consolidated draft's `<draftId>` in this tracker's rollup entry.

The bundle itself is drafted once, on the earliest thread, per [Step 5](../screening-and-proposal.md#consolidated-receipts-for-multi-tracker-imports);
its coherence check (one reply that characterises every tracker correctly) stays the model's.
In the `render-recap` state, list the bundle's draft under every candidate it covers: the recap shows it once.
