<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "groups": [
    {
      "strategy": "unused-import | type-annotation | unused-variable | doc-coverage | dead-code | style | line-length | other",
      "findings": ["<finding_id_1>", "<finding_id_2>"]
    }
  ],
  "security_flagged": ["<finding_id>"]
}
```

`security_flagged` lists any finding IDs that carry a CVE label or security classification. These must not appear in `groups`.
`groups` contains only non-security findings, each assigned to the strategy that best matches the rule.
Do not include any text outside the JSON object.
