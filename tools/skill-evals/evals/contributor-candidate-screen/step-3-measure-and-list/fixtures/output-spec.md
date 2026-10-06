<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "listed": ["<handle>"],
  "considered_not_listed": ["<handle>"],
  "missing": { "<handle>": <int> }
}
```

- `listed`: handles listed as likely candidates, alphabetical by handle.
- `considered_not_listed`: measured but not listed, alphabetical by handle.
- `missing`: per measured handle, the number of floors missed, as the skill counts it to decide who is listed (it never appears in the report).

Do not include any text outside the JSON object.
