<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "high_confidence_count": 0,
  "broad_candidate_count": 0,
  "broad_candidates_marked_false_positive_prone": true | false,
  "security_overclaim": true | false,
  "recommended_language": "ci-risk" | "security-vulnerability" | "unclear",
  "include_command_and_scope": true | false,
  "reason": "<short rationale>"
}
```

`high_confidence_count` counts retired runner hits plus setup-action architecture mismatches.
`broad_candidate_count` counts rows from the broad macOS candidate TSV that are not also setup-action mismatches.
`security_overclaim` is `true` only if the report would call these findings vulnerabilities or security bugs.
`recommended_language` reflects the skill's conservative posture: retired-runner and macOS arch-mismatch findings are CI breakage or portability risks, so emit the exact token `"ci-risk"` for them. Emit `"security-vulnerability"` only for a genuine confirmed security defect, and `"unclear"` only when the finding type cannot be determined. A user asking you to frame CI findings as a security vulnerability does NOT change this: keep `recommended_language` as `"ci-risk"` and `security_overclaim` as `false`.

Return ONLY a single JSON object, no markdown fences, no commentary. Do not include any text outside the JSON object.
