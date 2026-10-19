<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Receipt draft on the `oauth_curl` backend (preferred)

Read from [Step 7 item 4](../apply.md#step-7--apply-confirmed-imports).

**The draft must be created as a reply on the inbound thread** via the project's configured drafting backend per
[`tools/gmail/draft-backends.md`](../../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend).
The preferred `oauth_curl` backend uses `--thread-id` directly and preserves URLs verbatim.

**Before drafting, check for an existing pending draft** on the inbound thread per
[`draft-backends.md` § *Detecting drafts that already exist on a thread*](../../../../../tools/gmail/draft-backends.md#detecting-drafts-that-already-exist-on-a-thread)
— run **both** `mcp__claude_ai_Gmail__list_drafts` and
`mcp__claude_ai_Gmail__get_thread(threadId=<candidate>,
messageFormat='MINIMAL')` (scan messages for `DRAFT` labels),
so thread-attached drafts hidden from the global Drafts folder are not missed.
If a pending draft already exists, surface it to the user instead of shadowing it with a second draft.
This is the one thread re-read in Step 7, deliberately fresh rather than reused from Step 2a:
a draft or a new reporter message can land between the scan and the apply.
