<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `deterministic_flag` → `rerun` — rows 10 and 11, systemic CI failure

**Fires when** CI failure is the only signal and every failure (row 10) or some failure (row 11) also fails on at least two of the ten most recently merged PRs.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; `details.failed_checks` lists the failures.

**Proposed action:** `rerun` — [`actions/rerun.md`](../actions/rerun.md).

## Why

The PR is not the cause; the rerun is the right move.
Row 11 is the same logic with lower confidence.
The main-branch sample is fetched once per session; a check name failing on two or more of the ten is "systemic".
