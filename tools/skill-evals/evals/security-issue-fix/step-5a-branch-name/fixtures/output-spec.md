<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **branch name proposal** sub-step of `security-issue-fix`.

A proposed branch name is provided. Validate it and return a JSON object.

```json
{
  "branch_name": "<string>",
  "valid": true | false,
  "forbidden_pattern_found": "<string or null>",
  "recommendation": "<string or null>"
}
```

Field rules:
- `valid`: `false` if the name contains `CVE-`, `cve-`, `security-fix`, `vulnerability`, `advisory`, or `security` as a standalone word.
- `forbidden_pattern_found`: the specific forbidden pattern matched, or `null` if clean.
- `recommendation`: a corrected alternative slug when `valid` is `false`, else `null`.
