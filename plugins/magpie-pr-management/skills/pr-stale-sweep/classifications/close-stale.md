<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `CLOSE-STALE`

**Fires when** either the PR has had no real activity for at least `hard_close_days`, or it is idle past `close_days` with a standing nudge at least 7 days old and no author activity since.
[`stale-sweep classify`](../../../../../tools/pr-management/src/pr_management/stale_sweep/classify.py) decided it; `details.basis` is `hard_close` or `nudged`.

**Action:** post the rendered close notice, then — only after a **second** explicit confirmation — close (Steps 5–6). Never in bulk: the second confirmation is per PR, even after `all`.

## Why

The close notice carries `<!-- pr-stale-sweep-close -->`, not the nudge marker: a close notice is not a nudge, so a re-opened PR is nudged afresh rather than closed again on the strength of an old notice.
Any author activity after the nudge resets the clock — that PR is not here.
