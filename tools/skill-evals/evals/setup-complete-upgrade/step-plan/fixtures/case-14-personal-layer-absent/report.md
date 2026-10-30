<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Magpie installed (marketplace), not adopted and not configured: no personal layer yet, no `.apache-magpie-overrides/`, no committed lock. Isolated setup: configured.

Findings:
- slug: setup-config-needed. The personal layer `<git-common-dir>/apache-magpie/` does not exist yet; `setup config` would create it.
  Gather's sandboxed probe write into the directory itself failed because it does not exist; the probe write into its nearest existing parent, `<git-common-dir>/`, succeeded.
