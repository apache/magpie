<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "report": "<the full markdown report>",
  "has_surfacing_note": true | false
}
```

- `report`: the report exactly as it would be written.
- `has_surfacing_note`: whether the report states at the top that it only surfaces details about likely candidates, deliberately lists more people than the governing body would consider, is not a ranking, does not say whether anyone is ready, and that every decision is made by the governing body's members.

Do not include any text outside the JSON object.
