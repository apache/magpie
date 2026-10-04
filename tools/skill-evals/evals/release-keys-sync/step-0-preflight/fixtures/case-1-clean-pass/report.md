<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill keys-sync`):

```json
{
  "ok": true,
  "skill": "keys-sync",
  "blockers": [],
  "warnings": [],
  "values": {
    "fingerprint": "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD",
    "fingerprint_source": "release-management-config.md rm_key_fingerprint",
    "keys_file_url": "https://dist.apache.org/repos/dist/release/airflow/KEYS",
    "keyserver": "keys.openpgp.org"
  }
}
```

KEYS file content (excerpt from dist.apache.org):
  The file contains 12 existing key blocks for current PMC members.
  Fingerprint A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD does NOT appear
  anywhere in the KEYS file.

No overrides file found at .apache-magpie-overrides/release-keys-sync.md.
No snapshot drift detected.
