<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (verdict: proceed)
Step 1: PASS (verdict: proceed)

Key metadata from keyserver:
  fingerprint: B9F1E2D3C4A5A6B7C8D9E0F1FEDCBA9876543210
  uid: Maria Santos <msantos@example.org>
  algorithm: EdDSA
  bit_length: null (Ed25519 curve)
  created: 2024-01-20
  expiry: none
  strength_check: pass

Public key block (armoured, Ed25519, from keyserver):
-----BEGIN PGP PUBLIC KEY BLOCK-----

xjMEZ... [Ed25519 public key block, truncated for fixture] ...Santos
=qRsT
-----END PGP PUBLIC KEY BLOCK-----

keys_file_url: https://github.com/example-org/example-project/blob/main/KEYS
keyserver: keys.openpgp.org
project_dist_name: example-project

Note: keys_file_url points to a GitHub repository, not dist.apache.org.
This is a non-ASF adopter. Commands should use git rather than svn.
The KEYS file is in the repository at path: KEYS (root of the repo)
Repository: https://github.com/example-org/example-project

`release-management keys-sync render --step 2 --preflight <scratch>/keys-preflight.json --load <scratch>/keys-load.json --check <scratch>/keys-check.json --key-file <scratch>/fetched-key.asc --key-listing <scratch>/key-list.json` output (the Step 1 JSON is the key metadata above; the fetched file holds the block above):

```json
{
  "keys_block_to_append": "# Maria Santos <msantos@example.org>\n-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nxjMEZ... [Ed25519 public key block, truncated for fixture] ...Santos\n=qRsT\n-----END PGP PUBLIC KEY BLOCK-----",
  "svn_command_sequence": "# 1. Clone the repository holding KEYS (push to your fork instead if you lack write access)\ngit clone https://github.com/example-org/example-project.git /tmp/example-project-keys\ncd /tmp/example-project-keys\ngit checkout -b keys-sync-fedcba9876543210 origin/main\n\n# 2. Append the key block below to KEYS\n\n# 3. Commit, push and open the PR for review\ngit add KEYS\ngit commit -m \"Add Maria Santos <msantos@example.org> to KEYS (fingerprint: B9F1E2D3C4A5A6B7C8D9E0F1FEDCBA9876543210)\"\ngit push origin keys-sync-fedcba9876543210\ngh pr create --web --repo example-org/example-project --base main --title \"Add Maria Santos <msantos@example.org> to KEYS\"",
  "keyserver_upload_reminder": "Upload the public key to https://keys.openpgp.org/upload (or the keyserver's documented upload endpoint) before the vote opens, so voters and future verifiers can fetch it.",
  "proposed": true,
  "backend": "git",
  "atr_offer": false,
  "svn_keys_dir_url": null,
  "read": [
    "backends/git.md"
  ],
  "warnings": []
}
```
