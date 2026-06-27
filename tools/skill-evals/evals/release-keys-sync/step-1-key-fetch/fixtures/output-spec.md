<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 1 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked",
  "key_found": true | false,
  "fingerprint": "<fingerprint>",
  "uid": "<primary UID string or null>",
  "algorithm": "RSA" | "EdDSA" | "ECDSA" | "DSA" | null,
  "bit_length": <integer or null>,
  "created": "YYYY-MM-DD" | null,
  "expiry": "YYYY-MM-DD" | null,
  "strength_check": "pass" | "fail" | null,
  "strength_note": "<string or null>"
}
```

Grading rules:
- `verdict` must be `"proceed"` only when `key_found` is `true` AND `strength_check` is `"pass"`.
- `verdict` must be `"blocked"` when `key_found` is `false` (key not on keyserver) or when `strength_check` is `"fail"` (key below ASF floor).
- `key_found` must be `true` or `false` based on whether the keyserver returned a key.
- `strength_check` must be `null` when `key_found` is `false`.
- `strength_check` must be `"pass"` for RSA ≥ 2048 bits, EdDSA (Ed25519), and ECDSA (P-256+).
- `strength_check` must be `"fail"` for RSA < 2048 bits and DSA < 2048 bits.
- `bit_length` must be `null` for curve-based algorithms (EdDSA, ECDSA).
- `strength_note` must be non-null when `strength_check` is `"fail"`, and must explain why the key fails the ASF floor.
- No extra keys are permitted in the response.
