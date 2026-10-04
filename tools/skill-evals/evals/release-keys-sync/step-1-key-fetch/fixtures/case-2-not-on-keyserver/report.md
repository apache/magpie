<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (verdict: proceed)
Fetching fingerprint A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD from keys.openpgp.org

Keyserver response:
  HTTP 404 — no key found for fingerprint A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD
  on keys.openpgp.org.

The RM may not have uploaded their public key to the keyserver yet,
or the configured fingerprint may be incorrect.

Output of `python3 <skill-dir>/scripts/check_key.py --key-file fetched-key.asc --fingerprint A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD` (the keyserver returned 404, so the saved file is empty):

```json
{
  "verdict": "blocked",
  "key_found": false,
  "fingerprint": "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD",
  "uid": null,
  "algorithm": null,
  "bit_length": null,
  "created": null,
  "expiry": null,
  "strength_check": null,
  "strength_note": null
}
```
