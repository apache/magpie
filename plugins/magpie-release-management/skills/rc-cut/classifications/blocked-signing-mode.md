<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Blocked — signing mode inconsistent

**Likely cause:** `automated_release_signing: enabled` (where the organization offers automated signing) without `reproducibility_source: on` / `reproducibility_binaries: byte-identical`;
where it does not, the setting is ignored and `signing_mode` stays `rm-key`.

**Remediation:** set `automated_release_signing: off` (or `requested`) until the conditions hold; see `release-prepare automated-signing`.
