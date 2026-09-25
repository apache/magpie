<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "decision": "run" | "ask",
  "subaction": "<sub-action name, or null>",
  "suggestions": ["<sub-action name>"]
}
```

- `decision` — `"run"` when the argument names a sub-action from the
  table exactly and the skill proceeds into it; `"ask"` when it does not,
  and the skill prints the unknown-sub-action message and waits.
- `subaction` — the sub-action that runs when `decision` is `"run"`;
  `null` when `decision` is `"ask"`. A near match is never filled in
  here: nothing runs until the user confirms it.
- `suggestions` — the sub-actions offered as *"did you mean"*, sorted
  alphabetically. Empty when `decision` is `"run"`, and empty when no
  sub-action is close enough to suggest.

Do not include any text outside the JSON object.
