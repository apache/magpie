<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 9 — Reproducibility

From `release-management verify-rc repro`. `differs` and a moved tag are always `FAIL`.

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 9 WARN — `content-identical` | RM built with a plain `git archive` or a different tool version instead of `repro-archive build` | Accept for this RC in RM-key mode; RM switches to `repro-archive build` for the next one. Under automated signing this is `FAIL` |
| Step 9 FAIL — `differs` | Artefact built from a dirty checkout, a different ref, or a non-deterministic `custom` build | `-1`; RM rebuilds at the tag from a clean checkout (`release-rc-cut` Step 2b catches this before signing) |
| Step 9 FAIL — tag moved | `<rc-tag>` no longer points at the commit recorded on the planning issue | `-1`; the RM explains and cuts a new RC number — never re-point an RC tag |
| Step 9 FAIL — convenience artefact `DIFFERS` | The artefact is not what the voted source produces: the build embeds timestamps, host paths or an unpinned toolchain, or was built from a different tree | The artefact is not good to publish. RM honours `SOURCE_DATE_EPOCH`, pins the toolchain (`ARFLAGS=Dcvr`, `ranlib -D`), or documents the divergence under the entry's `known_divergences`; `release-promote` withholds its publish command until a verify-rc run reproduces it |
| Step 9 SKIP but `automated_release_signing: enabled` | Misconfiguration — the check cannot be skipped in that mode | Re-run without `--skip-repro`; the report refuses to carry an attestation |
