<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `SKIP-NUDGE-PENDING`

**Fires when** the PR carries a standing nudge (no author activity since) but its close window has not run out: it is idle less than `close_days`, or the nudge is under 7 days old.
[`stale-sweep classify`](../../../../../tools/pr-management/src/pr_management/stale_sweep/classify.py) decided it; `remaining_days` is how long until it becomes `CLOSE-STALE` if nothing happens.

**Action:** none. Mention it in the recap; the author has the question.
