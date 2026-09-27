<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "shortlist": ["<handle>"],
  "considered_not_shortlisted": ["<handle>"],
  "missing": { "<handle>": <int> }
}
```

- `shortlist`: shortlisted handles, alphabetical.
- `considered_not_shortlisted`: measured but not shortlisted, alphabetical.
- `missing`: per measured handle, the number of floors missed, as the skill counts it.

Do not include any text outside the JSON object.
