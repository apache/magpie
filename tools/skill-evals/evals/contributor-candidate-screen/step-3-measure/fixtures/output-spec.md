<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "in_report": ["<handle>"],
  "compared_with_floors": <bool>
}
```

- `in_report`: handles whose data goes into the report, alphabetical by handle.
- `compared_with_floors`: whether any measured person's counts are compared with the floors after the pre-filter.

Do not include any text outside the JSON object.
