<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Receipt draft on the `claude_ai_mcp` backend (credentials-missing fallback)

Read from [Step 7 item 4](../apply.md#step-7--apply-confirmed-imports).

The `claude_ai_mcp` backend is discouraged because it rewrites embedded URLs into Google tracking redirects
(see [`draft-backends.md`](../../../../../tools/gmail/draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects));
as a credentials-missing fallback it takes the chronologically-last message ID
(`messages[-1].id` from the fresh `get_thread` read made for the existing-draft check below — do not fetch the thread a second time)
and passes it to `mcp__claude_ai_Gmail__create_draft` as `replyToMessageId`.
Surface in the proposal which backend was used and which path the draft took (thread-attached vs subject fallback).

The existing-draft check is the same as on [`oauth_curl`](oauth_curl.md).
The same result supplies `messages[-1].id` for the fallback backend above.
