<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-keys-sync — references

- [`docs/release-management/process.md`](../../../../docs/release-management/process.md) —
  Step 3 context.
- [`docs/release-management/spec.md`](../../../../docs/release-management/spec.md) —
  `release-keys-sync` per-skill specification.
- [`<project-config>/release-management-config.md`](../../../magpie-setup/templates/release-management-config.md) —
  adopter keys this skill reads (`keys_file_url`, `keys_file_branch`, `keyserver`,
  `rm_key_fingerprint`).
- [`tools/release-verify`](../../../../tools/release-verify/README.md) —
  `release-verify list-keys`, the fingerprints and UIDs of the KEYS file and of the fetched key.
- [`tools/release-management`](../../../../tools/release-management/README.md) —
  `release-management keys-sync verdict` / `check` / `render`.
- [`tools/release-config`](../../../../tools/release-config/README.md) —
  `release-config preflight` / `load --skill keys-sync`.
- `release-prepare` — upstream step; planning issue should be open.
- `release-rc-cut` (proposed) — downstream step; KEYS must be updated
  before RC artefacts are signed.
- [ASF release-signing](https://infra.apache.org/release-signing.html) —
  key strength requirements and keyserver policy.
- [ASF release policy](https://www.apache.org/legal/release-policy.html) —
  policy governing release artefacts and signing.
