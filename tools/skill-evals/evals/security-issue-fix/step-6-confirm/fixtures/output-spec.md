<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are executing Step 6 (confirm plan) in isolation. The implementation
plan and the user's confirmation response are provided in the user turn as
mock data. Parse the confirmation and return ONLY valid JSON with these
fields:

```json
{
  "action": "apply" | "edit" | "cancel",
  "edit_request": "<description of requested change, or null>",
  "items_applied": [<int>, ...],
  "items_skipped": [<int>, ...]
}
```

- `action` is `"cancel"` if the user responded with `none`, `cancel`, or
  equivalent. Both arrays are empty.
- `action` is `"apply"` if the user confirmed the full plan or selected
  items with `all` or a numbered list.
- `action` is `"edit"` if the user requested a change to the plan. In this
  case `edit_request` captures what they want changed; `items_applied` and
  `items_skipped` are both empty (the plan must be regenerated before
  applying).
- When `action` is `"apply"`, `items_applied` lists confirmed plan sections
  (1=branch+base, 2=files, 3=commit+title, 4=test-plan, 5=backport,
  6=newsfragment, 7=PR body). `items_skipped` lists any omitted.

Do not include any text outside the JSON object.
