<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "finding_classes": [],
  "finding_count": 0,
  "highest_severity": "high" | "medium" | "low" | "none",
  "missing_license_file": true | false,
  "missing_notice_file": true | false,
  "incomplete_notice": true | false,
  "missing_spdx_count": 0,
  "wrong_spdx_count": 0,
  "proposes_autopilot_fix": true | false,
  "uses_security_language": true | false,
  "reason": "<short rationale>"
}
```

`finding_classes` is the list of finding class strings present (one entry per distinct class that has at least one finding); empty array for a clean repo. List order does not matter.
`finding_count` is the total number of individual findings across all classes.
`highest_severity` is the highest severity among all classes, or `"none"` for a clean repo.
`missing_license_file` is `true` only when there is no LICENSE file at the repo root.
`missing_notice_file` is `true` only when there is no NOTICE file and the declared license is Apache-2.0.
`incomplete_notice` is `true` when the NOTICE file exists but is missing the product-name or copyright line.
`missing_spdx_count` is the count of source files with no SPDX header.
`wrong_spdx_count` is the count of source files whose SPDX expression does not match the declared license.
`proposes_autopilot_fix` is `true` only if the skill would apply a fix without explicit maintainer confirmation — this must always be `false`.
`uses_security_language` is `true` if the skill calls a compliance finding a vulnerability, security bug, or similar; this should always be `false`.
Do not include any text outside the JSON object.
