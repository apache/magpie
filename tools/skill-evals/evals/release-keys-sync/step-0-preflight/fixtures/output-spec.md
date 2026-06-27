<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "verdict": "proceed" | "blocked" | "noop",
  "blockers": ["<string>"],
  "noop_reason": "<string or null>",
  "fingerprint": "<40-hex-char fingerprint>",
  "keys_file_url": "<url>",
  "keyserver": "<keyserver host>"
}
```

Grading rules:
- `verdict` must be `"proceed"` when the fingerprint is not found in the KEYS file and config is complete.
- `verdict` must be `"noop"` when the fingerprint is already in KEYS with the same UID the keyserver reports.
- `verdict` must be `"blocked"` when config is missing, KEYS file is unreachable, or fingerprint is in KEYS with a different UID (key rolled).
- `blockers` must be an empty array when `verdict` is `"proceed"` or `"noop"`.
- `noop_reason` must be non-null when `verdict` is `"noop"` and must identify the UID already in KEYS.
- `noop_reason` must be null when `verdict` is not `"noop"`.
- `fingerprint`, `keys_file_url`, and `keyserver` must echo back the resolved values from config/overrides.
- No extra keys are permitted in the response.
