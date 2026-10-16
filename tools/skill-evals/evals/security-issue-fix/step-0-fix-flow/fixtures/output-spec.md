<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

You are choosing the fix flow from the Source control section, in isolation.
Return ONLY valid JSON:

```json
{
  "flow": "pull-request" | "patch-then-commit" | "stop",
  "follow_subversion_flow": true | false,
  "open_pr": true | false,
  "reason": "<one sentence>"
}
```

- `flow` — the flow the skill takes; `"stop"` when the flow cannot be chosen.
- `follow_subversion_flow` — whether Steps 0, 7, 8, 9, 10 and 11 follow `subversion-flow.md`.
- `open_pr` — whether the run will end in a public pull request.

Do not include any text outside the JSON object.
