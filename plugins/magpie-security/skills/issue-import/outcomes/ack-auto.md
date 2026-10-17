<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Receipt draft — `reporter_acknowledgement_model: auto`

`ack-decision` printed `draft_created: true`, `draft_auto_ack_tagged: true`, `auto_ack_tag` and `proposal_note`.

- **`auto`**: Draft the same receipt, but prepend `[auto-ack]`
  to the draft summary line and add a note in the Step 5
  proposal: *"acknowledgement_model=auto — this is the
  standard receipt template and may be sent without further
  triager review per your project's security-intake-config.md
  disclosure_governance"*. The **Never send** hard rule still
  applies — the skill creates a draft; `[auto-ack]` is a
  triager hint, not an auto-dispatch instruction. `window_days`
  substitution applies as in `manual`.

Then draft it per [Step 7 item 4](../apply.md#step-7--apply-confirmed-imports), exactly as for [`manual`](ack-manual.md).
