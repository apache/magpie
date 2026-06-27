<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 7 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "step": "version-consistency",
  "status": "PASS" | "FAIL",
  "expected_version": "<version>",
  "results": [
    {
      "file": "<manifest file path>",
      "extracted": "<version string found or null>",
      "match": true | false
    }
  ]
}
```

Grading rules:
- `status` must be `"FAIL"` if any `match` is `false` or any `extracted` is `null`.
- `status` must be `"PASS"` if all `match` values are `true` and all `extracted`
  values are non-null.
- `expected_version` must be the version string without the `-rcN` suffix
  (e.g. `"2.11.0"` for `2.11.0-rc1`).
- A version string with a dev or snapshot suffix (e.g. `"2.11.0.dev0"`,
  `"2.11.0-SNAPSHOT"`) must cause `match` to be `false` — it is never acceptable.
- No extra keys are permitted in the response.
