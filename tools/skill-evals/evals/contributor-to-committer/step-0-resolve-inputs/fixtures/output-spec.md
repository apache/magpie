<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "login": "<validated login, or null if rejected>",
  "target": "committer | pmc",
  "window_months": <integer>,
  "upstream": "<owner/repo>",
  "login_rejected": true | false,
  "rejection_reason": "<one sentence, or null>"
}
```

- `login`: the validated GitHub handle, verbatim; null when rejected
- `target`: resolved target — `committer` or `pmc`
- `window_months`: integer window, from argument or config or default 6
- `upstream`: the `owner/repo` string from project config
- `login_rejected`: true when the login fails validation and the skill must stop
- `rejection_reason`: one sentence explaining why, or null

Do not include any text outside the JSON object.
