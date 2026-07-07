<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are executing Step 6 (recap) in isolation. The results of the apply
phase are provided in the user turn as mock data. Compose the recap and
return ONLY valid JSON with these fields:

```json
{
  "kept_issue_number": <int>,
  "dropped_issue_number": <int>,
  "cve_json_regenerated": true | false,
  "blockers": ["<string>", ...]
}
```

`blockers` lists any issues surfaced during the merge (CWE conflict,
unconfirmed credits, etc.) that the user must still resolve.
Empty array when no blockers.

Do not include any text outside the JSON object.
