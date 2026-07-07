<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "method": "maintainer-pointer | stack-trace | symbol-grep | subagent-exploration",
  "candidate_files": ["<file1>", "<file2>"],
  "confidence": "high | medium | low"
}
```

`method` is the first method from the priority list that produced results.
`confidence` is high when a maintainer pointer or stack trace named the exact file; medium for symbol-grep; low for exploration.
Do not include any text outside the JSON object.
