<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (verdict: proceed)
Fetching fingerprint A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD from keys.openpgp.org

Keyserver response:
  Key found: yes
  Primary UID: Brendan Ngan <bngan@apache.org>
  Algorithm: RSA
  Bit length: 4096
  Created: 2022-03-15
  Expiry: none
  Subkeys: 1 encryption subkey (RSA 4096)

Today's date: 2026-06-19
Key expires: never

Output of `python3 <skill-dir>/scripts/check_key.py --key-file fetched-key.asc --fingerprint A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD`:

```json
{
  "verdict": "proceed",
  "key_found": true,
  "fingerprint": "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD",
  "uid": "Brendan Ngan <bngan@apache.org>",
  "algorithm": "RSA",
  "bit_length": 4096,
  "created": "2022-03-15",
  "expiry": null,
  "strength_check": "pass",
  "strength_note": null
}
```
