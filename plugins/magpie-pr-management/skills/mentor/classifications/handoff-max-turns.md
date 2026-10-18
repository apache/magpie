<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hand-off trigger 1 — the thread reached `max_agent_turns`

`mentor assess` returned `outcome: handoff` with `handoff.trigger: 1`; `handoff.matched` is what fired it.

The agent has posted `max_agent_turns` comments (default 2) and the thread is still open. The next move is a hand-off, not another draft.

The triggers are checked in the order 4 → 3 → 1 → 2 on every new contributor turn; the first that fires wins.
Next: write the hand-off — [`hand-off-comment.md`](hand-off-comment.md).
