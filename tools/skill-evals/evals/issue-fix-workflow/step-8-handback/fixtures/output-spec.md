<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "has_issue_key": true | false,
  "has_branch_name": true | false,
  "has_targeted_test_result": true | false,
  "has_module_test_result": true | false,
  "has_diff_scope_summary": true | false,
  "has_open_questions": true | false
}
```

Do not include any text outside the JSON object.
