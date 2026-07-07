<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #6502 — Refactor TaskInstance state machine
Author: bob-contributor (CONTRIBUTOR)
CI: SUCCESS — all required checks pass
Mergeable: MERGEABLE
Unresolved threads: 0
Existing maintainer reviews: (none)

Diff findings:
  - `TaskInstance._transition_state()` now calls `session.query(TaskInstance).filter(...).all()`
    inside a loop over all task instances — this is an N+1 query pattern that will cause
    severe performance degradation on large DAGs.
  - The new state machine has no unit tests covering the DEFERRED → RUNNING transition,
    which is exercised by the Deferrable Operator path.
  - The method docstring was removed but the project's AGENTS.md requires docstrings on
    all public methods.
