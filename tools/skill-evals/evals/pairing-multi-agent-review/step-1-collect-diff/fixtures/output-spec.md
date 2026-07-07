<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "resolved_base": "<ref or SHA>",
  "files_changed": 0,
  "lines_added": 0,
  "lines_removed": 0,
  "diff_empty": true | false,
  "stop_reason": "<message when diff_empty is true, else null>"
}
```

`diff_empty` is true when the diff is empty and the skill should stop without spawning sub-agents.
`stop_reason` is the human-facing message in that case; null otherwise.
`resolved_base` is the explicit base ref or merge-base SHA, or the literal `"staged"` when the `staged` argument is set.
Do not include any text outside the JSON object.
