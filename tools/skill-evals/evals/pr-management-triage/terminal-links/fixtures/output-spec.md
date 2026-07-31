<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "display": "<visible PR reference>",
  "target": "<canonical pull-request URL>",
  "mode": "osc8" | "plain"
}
```

Use `osc8` only when the supplied environment supports terminal hyperlinks.
Use `plain` when the environment requires the fallback. Do not include any
text outside the JSON object.
