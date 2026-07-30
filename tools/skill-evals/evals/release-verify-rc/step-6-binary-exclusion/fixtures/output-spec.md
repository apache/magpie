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
- `expected_binaries` lists files that match a prohibited pattern but are
  marked known-and-accepted in the `release-build.md` Binary-exclude list;
  these are EXPECTED-BINARY, not PROHIBITED.
- `paste_recipe` must be a non-empty string with a `find` that includes the
  fixed baseline (`.class`, `.jar`, `.so`, `.dylib`, `.dll`, `.exe`, `.pyc`,
  `__pycache__`) and any extra globs from `release-build.md` beyond that
  baseline.
- No extra keys are permitted in the response.
