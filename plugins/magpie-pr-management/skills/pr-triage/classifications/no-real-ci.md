<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `deterministic_flag` → `rebase` — row 16

**Fires when** no real CI context ran (only bot and labeler checks), the PR is not conflicting, and the author is not first-time.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; the real-CI patterns come from `real_ci_patterns`.

**Proposed action:** `rebase` — [`actions/rebase.md`](../actions/rebase.md).

## Why

Two reasons this happens:

- A first-time contributor's real CI held in `action_required` — but row 1 catches that, so reaching row 16 means the author is not first-time and the index was empty.
- A workflow path filter excluded every workflow for this diff. Rare but real for diffs touching only docs or configs.

`rebase` re-triggers the whole CI matrix. If the path-filter explanation is right, the rerun is harmless and the PR falls through to `passing` next time.
