<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `SKIP-READY-LABEL`

**Fires when** the PR carries the configured `ready for maintainer review` label.
[`stale-sweep classify`](../../../../../tools/pr-management/src/pr_management/stale_sweep/classify.py) decided it, from the label list as read for this sweep — re-confirm it is still absent before posting on any other PR.

**Action:** none. The label means the PR is waiting on maintainers; `pr-management-triage` Sweep 4 owns stale ready PRs.
