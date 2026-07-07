<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "valid": <count of successfully parsed verdict.json files>,
  "errors": [
    {"key": "<KEY>", "error": "<parse error description>"}
  ],
  "total_files": <total count of verdict.json files found>
}
```

Do not include any text outside the JSON object.
