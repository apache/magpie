<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "report": "<the full markdown report>",
  "has_floor_note": true | false
}
```

- `report`: the report exactly as it would be written.
- `has_floor_note`: whether the report states at the top that it is a floor for noticing candidates, never a decision.

Do not include any text outside the JSON object.
