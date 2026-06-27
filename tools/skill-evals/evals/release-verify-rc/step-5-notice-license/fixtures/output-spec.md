<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 5 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "step": "notice-license",
  "status": "PASS" | "WARN" | "FAIL",
  "notice_present": true | false,
  "license_present": true | false,
  "notice_diff_lines": <integer | null>,
  "license_diff_lines": <integer | null>,
  "diff_summary": "<one-line description>"
}
```

Grading rules:
- `status` must be `"FAIL"` if either `notice_present` or `license_present` is `false`.
- `status` must be `"WARN"` when both files are present but the diff shows material
  changes (more than version-string-only changes).
- `status` must be `"PASS"` when both files are present and the diff is empty or
  trivially small.
- `notice_diff_lines` and `license_diff_lines` are the number of diff lines when a
  previous release was found; `null` when no previous release was found.
- `diff_summary` must be a non-empty one-line description of the changes or
  "no diff — no previous release found" or "no changes".
- No extra keys are permitted in the response.
