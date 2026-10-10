<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hand-off trigger 2 — the contributor pushed back on a why-answer

`mentor assess` returned `outcome: handoff` with `handoff.trigger: 2`; `handoff.matched` is what fired it.

The agent answered a why-question once (the why-question template) and the contributor's next message disagrees. The skill answers the *why* once; it does not argue.

The triggers are checked in the order 4 → 3 → 1 → 2 on every new contributor turn; the first that fires wins.
Next: write the hand-off — [`hand-off-comment.md`](hand-off-comment.md).
