<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "checks": [
    {
      "n": <1-11>,
      "status": "✓" | "✗" | "⚠" | "unchecked",
      "evidence": "<one-line summary: file paths, version strings, or command output>"
    }
  ],
  "hard_stop": true | false,
  "ask_for_framework_path": true | false
}
```

`checks` holds exactly eight entries, for checks 1, 2, 3, 4, 5, 6, 8 and 11, in that order, each with its final status once any `unknown` part is finished from the reads shown.
`hard_stop` is true when the run must stop and the operator upgrade before anything else.
`ask_for_framework_path` is true when the user has to be asked for the path of their framework checkout.
Do not include any text outside the JSON object.
