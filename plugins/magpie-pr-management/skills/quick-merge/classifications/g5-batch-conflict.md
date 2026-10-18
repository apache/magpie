<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `gate:G5` — conflicting in the batch

The batch already reports `CONFLICTING`: a cheap early cull of the obviously-conflicted PRs.
Every other mergeability verdict waits for the live read (the suffixed `gate:G5-*` reasons), because GitHub reports `UNKNOWN` or `BLOCKED` for most of a batched ready queue — gating on the batch value once dropped 177 of 204 ready PRs, almost none of them conflicting.
Gate drops are reported as counts; read this only when the maintainer asks why a PR is not a candidate. [`quick-merge screen`](../../../../../tools/pr-management/README.md#quick-merge-screen--pr-management-quick-merge) applied the gate.
