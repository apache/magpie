<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Receipt draft — `reporter_acknowledgement_model: manual`

`ack-decision` printed `draft_created: true`, `draft_auto_ack_tagged: false`.

- **`manual` (default)**: Draft the receipt-of-confirmation
  reply for triager review. When composing or customising the
  canned body, substitute `window_days` (from the observed-
  state bag, default 90) wherever the canned response
  references the CVD deadline — e.g. "we expect to have this
  resolved within `window_days` days".

Then draft it per [Step 7 item 4](../apply.md#step-7--apply-confirmed-imports): the reveal-before-send check, the existing-draft check, a reply on the inbound thread through the configured backend, and **never send**.
