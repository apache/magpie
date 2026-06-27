<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "step": "signatures",
  "status": "PASS" | "FAIL",
  "results": [
    {
      "file": "<artefact filename>",
      "sig_file": "<artefact>.asc",
      "classification": "PASS" | "KEY-NOT-IN-KEYS" | "FAIL",
      "fingerprint": "<key fingerprint or null>",
      "key_in_keys": true | false
    }
  ],
  "paste_recipe": "<multi-line shell commands>"
}
```

Grading rules:
- `status` must be `"FAIL"` if any `classification` is not `"PASS"`.
- `status` must be `"PASS"` if all `classification` values are `"PASS"`.
- `key_in_keys` must be `false` when `classification` is `"KEY-NOT-IN-KEYS"`.
- `paste_recipe` must be a non-empty string containing the gpg import and verify commands.
- A `KEY-NOT-IN-KEYS` classification must cause `status` to be `"FAIL"` — a key absent
  from the project trust anchor is never downgraded to a warning.
- No extra keys are permitted in the response.
