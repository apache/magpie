<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step A — not eligible (🪶 ASF-specific)

**Likely cause:** the project's organization does not offer automated release signing, or the build is not *demonstrably* reproducible yet.

**Remediation:** stop and list every `missing_conditions` entry as written; draft nothing.

- **Not ASF** (Step 0 blocked, or the organization is not `ASF`): no action and no description of the flow;
  automated signing is an ASF Infra offering, and the project keeps the RM-key flow.
- **Not demonstrably reproducible** (no `release-verify-rc` report with every artefact `identical`, or `reproducibility_*` not set as required):
  enable the checks in `release-build.md`, cut and verify an RC, then rerun `/release-prepare automated-signing`.
- **No ATR backend:** set `release_vote_backend: atr` or `release_dist_backend: atr`; the workflow template stages to ATR.

Return the Step A JSON with `eligible: false`, the `missing_conditions`, every draft `null`, `workflow_pr: null`, `config_diff: []`,
`filed_or_sent: false` and `proposed: true`.
