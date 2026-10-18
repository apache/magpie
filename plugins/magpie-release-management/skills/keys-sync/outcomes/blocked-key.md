<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 1 outcome — key `blocked`

`release-management keys-sync check` printed `verdict: "blocked"`. Stop at Step 1: no KEYS block, no command (Hard rules).
Surface the reason from the JSON; never judge the key by hand.

| `key_found` / `strength_note` | Remediation |
|---|---|
| `key_found: false` | The key is not on the keyserver (or the fingerprint is wrong): the RM uploads the public key to the keyserver first, then re-runs |
| below the ASF floor (RSA or DSA under 2048 bits), or an unaccepted algorithm or curve (secp256k1 included) | The RM generates a new key meeting the floor and updates `rm_key_fingerprint` |
| expired | The RM extends the expiry and re-uploads to the keyserver, or generates a new key and updates `rm_key_fingerprint` |
| revoked, invalid or disabled | The key never signs a release: the RM replaces it and updates `rm_key_fingerprint` |
| primary key has no signing capability, or no signing-capable key meets the admission rules (`signers` empty) | The RM adds a signing subkey that meets the floor (or fixes the weak, expired or revoked one), re-uploads the key, then re-runs |
