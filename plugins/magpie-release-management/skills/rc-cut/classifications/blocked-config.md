<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Blocked — configuration incomplete

| Symptom | Likely cause | Remediation |
|---|---|---|
| Pre-flight blocked — prohibited digest | `release-build.md` lists `md5` or `sha1` | Remove the prohibited digest from `release-build.md`; only `sha512` (required) and `sha256` (optional) are accepted |
| `release-build.md` missing or incomplete | Adopter has not filled out the template | Complete `<project-config>/release-build.md` before running this skill |
| `signing_key_fingerprint` empty | `rm_key_fingerprint` not set in user.md or config | Add `rm_key_fingerprint` to user.md (preferred) or `release-management-config.md` |
