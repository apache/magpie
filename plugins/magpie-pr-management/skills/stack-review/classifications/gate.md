<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The gate (Step 1)

`stack-review resolve` decided it: the lowest open layer `<k0>` (the merge gate and the comment target), the merged layers below it (not fetched, excluded from every check), the drafts (kept in every check; the headline marks them and the summary says they are not ready), whether `<viewer>` authored every layer, the CI cell per layer, and the trunk walk.
Print its `headline`, its `size_line` (approximate — the reading plan comes from the ledger after the fetch), the `trunk_sentence` when there is one (also as a gate row and as the opening of the verdict's first sentence), then its `gate` prompt.

The CI cell follows the Real-CI guard: `unverified` when the project's own test workflows have no run on the head, whatever the rollup says (bot-only `SUCCESS`, a draft whose workflows never ran) — never green; `cancelled` when the only non-green project-owned contexts were superseded runs — never red.
Configure `real_ci_patterns` in `<project-config>/pr-management-config.md` when the default reading (any context that is not a bot check or an auxiliary scan) is wrong for the project.

`self_authored: true` → say so; the summary is still offered.
Keep the `resolve` output: `snapshot` and `heads_digest` feed Step 6.
