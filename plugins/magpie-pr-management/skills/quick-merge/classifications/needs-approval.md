<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Needs your approval, then merge

Every gate is green, the PR is trivial, and the branch merges cleanly — but branch protection withholds it: the live state is `blocked` and the review decision is `REVIEW_REQUIRED`, so the missing piece is a committer approval.
**This is the skill's primary case, not a drop** — most ready PRs sit here.
The entry carries `approvals` and, when readable, `required_approvals`; if one approval will not reach the requirement, say so rather than implying the PR becomes mergeable.
With `enable_approve` on, offer `[A]pprove NN` — [`actions/approve.md`](../actions/approve.md) — then the merge command.
