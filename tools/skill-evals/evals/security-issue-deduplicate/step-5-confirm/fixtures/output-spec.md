<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are executing Step 5 (confirm with user) in isolation. The numbered
proposal list and the user's confirmation reply are provided in the user
turn as mock data. Parse the reply and return ONLY valid JSON with these
fields:

```json
{
  "action": "apply" | "cancel" | "ambiguous",
  "apply_items": [<int>, ...],
  "skip_items": [<int>, ...],
  "ambiguous_tokens": ["<string>", ...]
}
```

`apply_items` lists every proposal item that will be executed.
When `action` is `"cancel"`, all lists are empty.
`ambiguous_tokens` is empty unless `action` is `"ambiguous"`.

Do not include any text outside the JSON object.
