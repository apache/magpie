<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Receipt draft — covered by its thread's single receipt

`ack-decision` printed `draft_created: false` and a `rollup_receipt` with the bundle's `bundle_draft_id`.

- The candidate came from the same inbound thread as another tracker in this run,
  and that thread's one receipt (Step 5's *"One receipt per thread"*), already confirmed at Step 5, covers it.
  Cross-link that draft's `<draftId>` in this tracker's rollup entry.

The receipt is drafted once, on that thread, per [Step 5](../screening-and-proposal.md#one-receipt-per-thread--never-a-consolidated-receipt-across-threads).
A receipt never covers trackers from another thread, even one from the same reporter:
a `bundle_draft_id` whose draft sits on a different thread than this candidate's is a bug — stop and draft this candidate's own receipt on its own thread.
In the `render-recap` state, list the draft under every candidate it covers: the recap shows it once.
