<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Blocked — `archive_reviewed: false`

**Likely cause:** `export_ignore_reviewed` is unset in `release-build.md § Source archive`.

**Remediation:** run `release-prepare prep <version>`; its Step 2e reviews what ships and lands `.gitattributes` in the prep PR.
`--allow-unreviewed-archive` is the logged override: proceed only on it, and Step 4 records the override and why (Golden rule 7).
