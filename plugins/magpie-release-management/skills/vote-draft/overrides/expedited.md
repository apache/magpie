<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Override — `--expedited <reason>`

Accepted only when `vote_window_hours` is below 72; `release-config preflight` reports `expedited: true` (Golden rule 4).

**The reason is public.**
The `[VOTE]` thread and the planning issue are public, so until the advisory ships the reason names no CVE and does not call the release a security fix
([`AGENTS.md` § Confidentiality](../../../../../AGENTS.md#confidentiality-of-the-tracker-repository)).
Rewording it is your judgement, not the tool's: write it neutrally (*"Time-sensitive fix release"*), keep any approval the RM cited, and tell the RM what was left out.
Pass the reworded reason as `--expedited` to both renders.
When a render's `warnings` still flags the reason, reword it and render again; never present a body or comment carrying the flagged reason.

What the renders add:

- **Step 2** — the `[EXPEDITED: <reason>. ASF policy requires this deviation to be noted in the project's next board report.]` notice after the window line, and `expedited: true`.
- **Step 3** — the expedited variant: `(expedited)` in the header, the shortened window, the reason, and the board-report reminder.
- **Step 4** — restate the flag and the reason, and remind the RM to note the deviation in the project's next board report per ASF policy.
