<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-keys-sync — prerequisites

- **`rm_key_fingerprint` configured** — in `<project-config>/release-management-config.md` (under Signing § `rm_key_fingerprint`) or in `.apache-magpie-overrides/user.md` under `release_manager.gpg_fingerprint`, or passed via `--fingerprint <fp>`.
- **`keys_file_url` configured** — the URL of the project's KEYS file (e.g. `https://dist.apache.org/repos/dist/release/<project>/KEYS`), or overridden via `--keys-url <url>`.
  On GitHub, `keys_file_branch` names the branch when it contains `/` (see [`backends/git.md`](backends/git.md)).
- **`keyserver` configured** — defaults to `keys.openpgp.org`; overridable via the `keyserver` key in the config's Signing section or `--keyserver <host>`.
- **KEYS file and keyserver reachable** — both are needed for the fingerprint presence check and UID comparison.
- **`gpg` on `PATH`** for [`release-verify list-keys`](../../../../tools/release-verify/README.md), which reads the KEYS file and the fetched key in a throwaway `GNUPGHOME` (public keys only, never the user's keyring, no agent, no network).
