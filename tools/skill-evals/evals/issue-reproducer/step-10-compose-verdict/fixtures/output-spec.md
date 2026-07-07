<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "issue_key": "<ISSUE-KEY>",
  "classification": "<classification from step 7>",
  "nature": "<nature label>",
  "shape": "<shape from step 3>",
  "runtime_version": "<version string or null>",
  "command": "<verbatim command run>",
  "exit_code": <integer>,
  "wall_clock_seconds": <number>,
  "confirmed_by_maintainer": true | false
}
```

`confirmed_by_maintainer` is true only when a MEMBER/OWNER comment in the thread corroborates the verdict.
Do not include any text outside the JSON object.
