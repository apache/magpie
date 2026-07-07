<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "has_tool_and_count": true | false,
  "has_branch_name": true | false,
  "has_verify_result": true | false,
  "has_diff_scope_summary": true | false,
  "has_suppressed_findings": true | false,
  "has_open_questions": true | false
}
```

`has_tool_and_count` is true when the artefact names the audit tool and states how many findings were addressed.
`has_suppressed_findings` is true when the artefact includes a suppressed-findings section for the maintainer (even if the answer is "none"); when findings were suppressed with inline comments (e.g. `# noqa` / `# type: ignore`), that section lists them with the user-confirmed reason.
`has_open_questions` is true when the artefact includes an open questions section for the maintainer (even if the answer is "none").
Do not include any text outside the JSON object.
