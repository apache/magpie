<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `SKIP-NO-TIMESTAMPS`

**Fires when** GitHub returned no creation time for the PR, so there is no clock to measure inactivity from.
[`stale-sweep classify`](../../../../../tools/pr-management/src/pr_management/stale_sweep/classify.py) decided it.

**Action:** none. Mention it in the recap. Never infer dormancy from reading the PR itself.
