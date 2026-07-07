<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are executing Step 3 (confirm with user) in isolation. The numbered
proposal and the user's confirmation response are provided in the user
turn as mock data. Parse the confirmation and return ONLY valid JSON with
these fields:

```json
{
  "action": "apply" | "cancel",
  "items_applied": [<int>, ...],
  "items_skipped": [<int>, ...]
}
```

- `action` is `"cancel"` if the user responded with `none`, `cancel`, or
  equivalent. Both arrays are empty on cancel.
- `action` is `"apply"` if the user confirmed any items.
- `items_applied` lists item numbers that will be applied.
- `items_skipped` lists proposal item numbers not selected.

Do not include any text outside the JSON object.
