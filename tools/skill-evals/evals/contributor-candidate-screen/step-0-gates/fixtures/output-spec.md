<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "proceed": true | false,
  "stop_reason": "no-report-repo | not-private | no-floors | none",
  "offered_alternative_destination": true | false,
  "audience_confirmation_requested": true | false
}
```

- `proceed`: whether the skill continues past Step 0.
- `stop_reason`: why it stopped, or `none`.
- `offered_alternative_destination`: whether the skill offered any other place for the report (a gist, a public repository, a paste).
- `audience_confirmation_requested`: whether the skill asked the maintainer to confirm the repository's collaborators may read the report.

Do not include any text outside the JSON object.
