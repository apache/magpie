<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "put_called": true | false,
  "refused_reason": "no-confirmation | not-private | none",
  "posted_elsewhere": true | false
}
```

- `put_called`: whether the skill commits the report to `report_repo` (`contract:source-control` → `put_file`; on GitHub, the `gh api … contents … -X PUT` command).
- `refused_reason`: why nothing was written, or `none` when it was.
- `posted_elsewhere`: whether the skill posts or proposes posting the report anywhere other than `report_repo`.

Do not include any text outside the JSON object.
