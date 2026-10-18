<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `close-stale` — close a stale draft with its notice

Batchable, but each PR still shows its preview and waits for `Y` / `n`: these closes are rarely wrong, and very wrong when they are.

1. **Ready-label recheck** — the PR must not carry the ready label (Sweep 4 owns those). The [optimistic lock](deliver-note.md#0-optimistic-lock) read shows the labels; drop the PR from the sweep if it gained the label.
2. **Deliver the notice** — [`deliver-note.md`](deliver-note.md), action `close-stale`; the renderer picks the triaged or untriaged variant from the row.
3. **Close:**

   ```bash
   gh pr close <N> --repo <upstream>
   ```

No label: these are not quality-violation closes.
A mistaken close is reopened by the maintainer by hand; the skill never reverses its own mutation without a fresh confirmation.
