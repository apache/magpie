<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are executing Step 8 (recap) in isolation. The results of the apply
phase (Step 7) are provided in the user turn as mock data. Compose the
recap and return ONLY valid JSON with these fields:

```json
{
  "issues_created": [
    {"number": <int>, "url": "<full GitHub URL>"}
  ],
  "drafts_waiting": [
    {"draft_id": "<string>", "candidate": <int>}
  ],
  "skipped": [
    {"candidate": <int>, "reason": "<string>"}
  ],
  "cve_tool_bookkeeping_dropped": <int>,
  "next_step_reminder": true
}
```

Do not include any text outside the JSON object.
