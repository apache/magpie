<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "applied": ["<slug>"],
  "skipped": [{"id": "<slug>", "reason": "dropped" | "changed" | "failed"}],
  "second_plan": ["<slug>"],
  "bypass_calls": 0
}
```

The input lists the approved plan (each item with its slug and whether it is marked `[bypass]`), the user's reply, and what each item's pre-write re-check and run observed.

- `applied` — slugs of items that ran to completion, in plan order.
- `skipped` — items not applied, with the reason: `dropped` (the user dropped it), `changed` (the target changed since gathering), `failed` (the run errored).
- `second_plan` — slugs of newly found fixes that wait for a second approval, never applied in this run.
- `bypass_calls` — the number of Bash calls made with `dangerouslyDisableSandbox: true`.

Do not include any text outside the JSON object.
