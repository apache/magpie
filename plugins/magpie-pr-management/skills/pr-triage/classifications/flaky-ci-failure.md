<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `deterministic_flag` → `rerun` — row 13, likely flaky

**Fires when** CI failure is the only signal, there are at most 2 failures, and the branch is at most 50 commits behind its base.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; when it needs the commits-behind count it returns a `compare-behind` read under `needs` first.

**Proposed action:** `rerun` — [`actions/rerun.md`](../actions/rerun.md).

## Why

Most "two-failure" cases on an otherwise clean, up-to-date PR are flakes.
A branch far behind its base goes to the [fallback draft](quality-fallback.md) instead: the failure may be fixed on the base already.
