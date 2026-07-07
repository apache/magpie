<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are executing Step 7 item 4 (receipt-of-confirmation draft disposition)
in isolation. The observed-state bag and candidate details are provided in
the user turn. Determine whether to create a receipt draft, and whether
to tag it auto-ack, based on `reporter_acknowledgement_model`. Return ONLY
valid JSON with these fields:

```json
{
  "draft_created": <bool>,
  "draft_auto_ack_tagged": <bool>,
  "suppressed_reason": "<string or null>",
  "rollup_note": "<string or null>"
}
```

- `draft_created`: true when the skill creates a Gmail receipt-of-confirmation
  draft for this candidate; false when the draft is suppressed.
- `draft_auto_ack_tagged`: true only when `reporter_acknowledgement_model=auto`
  and a draft is created (the draft carries the `[auto-ack]` pre-approval note).
- `suppressed_reason`: the rollup-entry text recorded when `draft_created=false`;
  null otherwise.
- `rollup_note`: a Step 8 recap note when the draft was suppressed; null
  when the draft was created normally.

Do not include any text outside the JSON object.
