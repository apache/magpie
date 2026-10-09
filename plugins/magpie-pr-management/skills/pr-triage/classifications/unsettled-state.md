<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Unsettled state — row 22

**Fires when** GitHub has not settled the PR's state: `mergeable == UNKNOWN`, or the rollup disagrees with the checks (`SUCCESS` with failed checks, `FAILURE` with none — typically only cancelled contexts).
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it, before rows 17 and 19–20. The action is `skip`; retry next sweep.

Data anomalies usually mean GitHub has not finished computing the rollup or mergeability; a later sweep clears it.
Do not guess.
