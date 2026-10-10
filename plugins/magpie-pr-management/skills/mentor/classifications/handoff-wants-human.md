<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hand-off trigger 4 — the contributor asked for a human

`mentor assess` returned `outcome: handoff` with `handoff.trigger: 4`; `handoff.matched` is what fired it.

The contributor explicitly asked for non-agent attention ("can a maintainer", "can a real person", …). Always fires, and takes priority over the other three.

The triggers are checked in the order 4 → 3 → 1 → 2 on every new contributor turn; the first that fires wins.
Next: write the hand-off — [`hand-off-comment.md`](hand-off-comment.md).
