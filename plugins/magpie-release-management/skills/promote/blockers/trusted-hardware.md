<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Blocked — no trusted-hardware attestation (🪶 ASF-specific)

Only when `values.trusted_hardware_attestation_required` is `true` (`signing_mode: ci-automated`).

The planning issue must carry a `release-verify-rc` comment with the **Reproducibility validated on trusted hardware** attestation for *this* `<version>-rc<N>`
(every artefact `identical`, `--trusted-hardware` asserted by the committer).
Without it, the verdict's blocker says what to run:
`release-verify-rc <version>-rc<N> --trusted-hardware --post-to <planning-issue>`, on the committer's own machine.
Automated release signing requires every artefact to be rebuilt bit-by-bit identical on trusted hardware before publication
([Infra § Automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing)).
There is no override.
