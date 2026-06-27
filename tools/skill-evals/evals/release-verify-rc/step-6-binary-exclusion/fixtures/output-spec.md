<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 6 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "step": "binary-exclusion",
  "status": "PASS" | "FAIL",
  "prohibited_found": ["<path>"],
  "expected_binaries": ["<path>"],
  "paste_recipe": "<multi-line shell commands>"
}
```

Grading rules:
- `status` must be `"FAIL"` if `prohibited_found` is non-empty.
- `status` must be `"PASS"` if `prohibited_found` is empty.
- `expected_binaries` lists files that match a prohibited extension pattern but are
  explicitly listed in the `release-build.md` binary-exclude list; these are
  EXPECTED-BINARY, not PROHIBITED.
- `paste_recipe` must be a non-empty string with the find command to scan the
  unpacked artefact.
- No extra keys are permitted in the response.
