<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `bot_draft` → `promote-bot-draft` — Step 0.5

**Fires when** an open draft PR is authored by a bot login (`dependabot`, `renovate[bot]`, `github-actions`, anything ending in `[bot]`).
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it before pre-filter F2 drops the same logins from the main flow; a bot draft skipped here stays a draft and does not surface again.

**Proposed action:** `promote-bot-draft` — [`actions/promote-bot-draft.md`](../actions/promote-bot-draft.md): flip to ready for review and add the ready label.
Default keystroke `[A]ll`: the action is deterministic and bot authorship removes the contributor-conversation concern that motivates per-PR review elsewhere.
Golden rule 1b still applies — the guard refuses a head with runs awaiting approval.
