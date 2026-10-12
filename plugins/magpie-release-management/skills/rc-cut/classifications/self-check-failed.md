<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2b self-check failed

Any `differs` / `DIFFERS` stops the cut: the RM fixes the build (or documents the divergence) and rebuilds before signing anything.
An artefact that does not reproduce here is not good to sign:
it is not known to be what the tagged source produces, and `release-promote` will withhold its publication until a verify-rc run reproduces it.

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 2b `compare` → `content-identical` | Source artefact built with a plain `git archive` or another tool version, not `repro-archive build` | Rebuild with `repro-archive build` (or `repro-archive recipe`); under `ci-automated` this is a stop |
| Step 2b `compare` → `differs` | The artefact is not the tagged tree (built from a dirty checkout, wrong ref, or a non-deterministic `custom` build) | Rebuild at the tag from a clean checkout; fix the build; do not sign |
| Step 2b binary `DIFFERS` | Build embeds timestamps, paths or a non-pinned toolchain | Honour `SOURCE_DATE_EPOCH`, pin the toolchain, `ARFLAGS=Dcvr`; or switch to `documented-divergence` and list the divergence in `release-build.md` |

For `documented-divergence`, any difference not listed under the entry's `known_divergences` is a stop; listed ones are reported.
With `source_archive_method: custom`, `content-identical` is a warning to switch the build to `repro-archive build` or `repro-archive recipe`.
