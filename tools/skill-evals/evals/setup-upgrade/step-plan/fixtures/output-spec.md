<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "items": [{"group": "fix" | "update" | "add" | "check", "bypass": true | false, "id": "<slug>"}],
  "run_yourself": ["<slug>"],
  "still_open": ["<slug>"],
  "isolated_offer": true | false,
  "nothing_to_do": true | false
}
```

The gathered findings are mock output of the skill's Gather phase; each finding names its `slug`.
Use exactly those slugs as ids.

- `items` — the plan items the skill would offer for approval, in plan order (Fix, Update, Add, Check).
  `bypass` is true when the item needs `dangerouslyDisableSandbox: true`.
- `run_yourself` — slugs of findings the skill prints as commands for the user and never offers as plan items.
- `still_open` — slugs of findings the skill will not offer, with a reason, in the plan's *Still open* block.
- `isolated_offer` — true only when the isolated-setup offer is made in this plan message, which requires confirmed absence (the user-scope settings, read outside the sandbox, enable no sandbox; opt-out not set).
  A `configured: false` read inside the sandbox is unknown: the plan carries a `[bypass]` *Check* item to confirm it and `isolated_offer` is false.
- `nothing_to_do` — true only when there is nothing actionable, nothing for *Run these yourself*, and no isolated-setup offer is pending; a pending isolated-setup offer counts as actionable, so a plan whose only content is that offer has `nothing_to_do: false`.

Do not include any text outside the JSON object.
