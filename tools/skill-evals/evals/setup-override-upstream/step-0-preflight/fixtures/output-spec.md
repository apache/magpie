<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "state": "not-adopter-repo" | "no-drift" | "drift-ref" | "drift-method-url" | "drift-sha512",
  "action": "stop" | "proceed" | "propose-upgrade-nonblocking" | "propose-upgrade-blocking",
  "reason": "<one-sentence explanation>"
}
```

`state` describes the repo / lock-file situation:
- `not-adopter-repo`: no `.apache-magpie.lock` or no `.apache-magpie-overrides/` found.
- `no-drift`: both lock files present and in sync; no mismatch.
- `drift-ref`: same method + URL but committed ref differs from local fetched ref.
- `drift-method-url`: method or URL differ between committed and local locks.
- `drift-sha512`: `svn-zip` SHA-512 in committed lock does not match the local lock's recorded hash.

`action` follows directly from `state`:
- `not-adopter-repo` → `stop`.
- `no-drift` → `proceed`.
- `drift-ref` → `propose-upgrade-nonblocking` (⚠ sync needed; user may defer).
- `drift-method-url` → `propose-upgrade-blocking` (✗ full re-install needed; doubly important before designing an abstraction).
- `drift-sha512` → `propose-upgrade-blocking` (✗ security-flagged; investigate before proceeding).

Do not include any text outside the JSON object.
