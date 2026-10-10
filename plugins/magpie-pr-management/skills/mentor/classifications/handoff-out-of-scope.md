<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hand-off trigger 3 — the topic entered `out_of_scope_topics`

`mentor assess` returned `outcome: handoff` with `handoff.trigger: 3`; `handoff.matched` is what fired it.

The latest contributor message — or, before the agent's first turn, the title and recent thread — matches an `out_of_scope_topics` keyword (security, deprecation, licensing, …). Hand off without drafting.

The triggers are checked in the order 4 → 3 → 1 → 2 on every new contributor turn; the first that fires wins.
Next: write the hand-off — [`hand-off-comment.md`](hand-off-comment.md).
