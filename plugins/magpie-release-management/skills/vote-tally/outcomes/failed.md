<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Outcome — FAILED

The render's body says *"The vote has FAILED."*, that `<version>-<rcN>` will be rolled back, and proposes the planning-issue label `rc-rolled`.
The label is a proposal: apply it only after the RM confirms (Golden rule 1).
Non-binding `+1` votes never pass a vote, however many there are.

Next step: the RM rolls back, increments the RC, and re-runs from `release-rc-cut`.
