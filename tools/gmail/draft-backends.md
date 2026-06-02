<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gmail drafting backends](#gmail-drafting-backends)
  - [Why there are two](#why-there-are-two)
  - [How the skills pick a backend](#how-the-skills-pick-a-backend)
  - [Detecting drafts that already exist on a thread](#detecting-drafts-that-already-exist-on-a-thread)
  - [Limitations that apply to both backends](#limitations-that-apply-to-both-backends)
  - [Known issue — thread-attached drafts may not surface in the global Drafts folder when stacked](#known-issue--thread-attached-drafts-may-not-surface-in-the-global-drafts-folder-when-stacked)
    - [Recommended workflow when re-drafting on a thread that already carries a pending draft](#recommended-workflow-when-re-drafting-on-a-thread-that-already-carries-a-pending-draft)
    - [Concrete steps when the pile-up has already happened](#concrete-steps-when-the-pile-up-has-already-happened)
    - [When this rule does not apply](#when-this-rule-does-not-apply)
  - [Referenced by](#referenced-by)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gmail drafting backends

The skills create Gmail drafts via one of two backends, selected by the
user in `.apache-magpie-overrides/user.md` under
`tools.gmail.draft_backend`:

| Backend | Value | Thread attach? | Setup |
|---|---|---|---|
| claude.ai Gmail MCP | `claude_ai_mcp` (default, recommended) | **yes** — via `replyToMessageId` (a message ID resolved from the inbound thread) | none — works as soon as the Gmail connector is authenticated on claude.ai |
| OAuth + `curl` script | `oauth_curl` | **yes** — via `threadId` (and explicit `In-Reply-To` / `References` headers) | one-time Google OAuth client + refresh-token setup, automated via `uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-setup` — see [`oauth-draft/README.md`](oauth-draft/README.md) |

Both backends create **drafts** — never send. The human review-and-send
step is still required before any outbound message leaves the user's
Gmail.

## Why there are two

The first-party claude.ai Gmail MCP is easy to set up and now exposes
everything the skills need for reading, searching, listing drafts,
**and creating thread-attached drafts** via `replyToMessageId`. It is
the default and the recommended backend for almost every adopter.

Historically the MCP's `create_draft` tool did not plumb through a
`threadId` parameter, which forced thread-attached drafts down the
`oauth_curl` path. That gap closed when the MCP added
`replyToMessageId` (a Gmail *message* ID — Gmail attaches the draft
to the conversation containing that message). The `oauth_curl`
backend remains in the toolchain because it offers two capabilities
the MCP still does not:

- **`threadId`-keyed draft creation** — useful when only a `threadId`
  is on hand (e.g. from an old tracker rollup) and re-fetching the
  thread to extract the latest message ID is not worth a round-trip.
- **Bulk read/modify operations** — `oauth-draft-mark-read`
  (label-modify on a query result set) has no MCP equivalent.

If you do not need either of those, **stay on the default
`claude_ai_mcp` backend**. The OAuth setup, refresh-token rotation,
and credentials-on-disk overhead is no longer required for thread
attachment alone.

## How the skills pick a backend

Every skill step that says *"create a Gmail draft via
`mcp__claude_ai_Gmail__create_draft`"* means *"create a draft via the
project's configured drafting backend"*.

**Default — `claude_ai_mcp` with `replyToMessageId`.** This is the
recommended path. Resolution:

1. **Resolve the latest message ID on the inbound thread.** Call
   `mcp__claude_ai_Gmail__get_thread(threadId=<inbound>,
   messageFormat='MINIMAL')` and take the `id` of the
   chronologically-last message. The tracker stores `threadId` (per
   the existing *security-thread* body field convention); the
   message-ID resolution is one extra round-trip and the skills
   absorb it.
2. **Create the draft.** Call
   `mcp__claude_ai_Gmail__create_draft(..., replyToMessageId=<that
   message id>)`. The draft attaches to the inbound thread on the
   sender's Gmail and surfaces in both the conversation view and the
   global Drafts folder.
3. **Fallback — omit `replyToMessageId`.** When the latest message
   cannot be resolved (thread archived, deleted, or stale `threadId`),
   create the draft with `replyToMessageId` omitted and rely on
   subject-matched threading (`Re: <root subject>` plus the recipient's
   own `In-Reply-To` / `References` chain). See
   [`threading.md`](threading.md#fallback--subject-matched-draft-when-replytomessageid-is-unavailable).

**Opt-in — `oauth_curl` for the cases the MCP cannot serve.** A user
who has explicitly set `tools.gmail.draft_backend: oauth_curl` and
who has a credentials file on disk:

1. **Probe for `oauth_curl` credentials** in this order:
   - `tools.gmail.oauth_credentials_path` from
     `.apache-magpie-overrides/user.md` when set;
   - the `$GMAIL_OAUTH_CREDENTIALS` environment variable;
   - the default path `~/.config/apache-steward/gmail-oauth.json`.

   The probe is a single `test -f <path>` — actually parsing the file
   or doing a token-refresh probe at this stage would burn HTTP
   round-trips on every draft.
2. **If credentials are found → use `oauth_curl`.** Invoke
   `uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-create`
   with `--thread-id`, `--to`, `--cc`, `--subject`, `--body-file` —
   see [`oauth-draft/README.md`](oauth-draft/README.md) for the full
   shape.
3. **If credentials are not found despite the user opting in →
   fall back to `claude_ai_mcp` and surface the missing-credentials
   warning.** Do not silently swallow the configuration mismatch.

The skills **surface which backend was used** in the proposal / recap
so the user can tell at a glance how the draft is threaded. The format
is one line:

> *Draft created via `claude_ai_mcp` (replyToMessageId-attached to
> message `<msg-id-prefix>...` on thread `<thread-id-prefix>...`)*

or

> *Draft created via `oauth_curl` (threadId-attached on
> `<thread-id-prefix>...`)*

or, when fallback kicks in:

> *Draft created via `claude_ai_mcp` (subject-matched fallback —
> `<reason: thread archived / latest message unresolved / etc.>`)*

## Detecting drafts that already exist on a thread

Before drafting a reply on a thread, skills check whether a pending
draft already exists so they do not silently shadow it (the claude.ai
MCP cannot update or delete drafts; see
[`operations.md`](operations.md#hard-limitation--no-update-no-delete)).
Run **both** detection paths and treat any hit as *"a draft already
exists; surface it to the user before drafting a new one"*:

- **List drafts globally.** Call `mcp__claude_ai_Gmail__list_drafts`,
  optionally narrowed by `query: "<recipient-email>"` or a
  distinctive subject substring. Both `claude_ai_mcp`-with-
  `replyToMessageId` drafts and `oauth_curl` drafts surface here, as
  do legacy MCP drafts created without `replyToMessageId` (which live
  as standalone server-side conversations).
- **Read the thread directly.** Call

  ```text
  mcp__claude_ai_Gmail__get_thread(threadId: "<inbound-thread-id>", messageFormat: MINIMAL)
  ```

  and scan the returned messages for any whose `labelIds` (or the
  snippet's metadata) include `DRAFT`. This catches thread-attached
  drafts that — under the pile-up condition described below — may
  not be navigable from the global Drafts folder.

`list_drafts` alone is not sufficient when thread-attached drafts
are involved (either backend); always do the per-thread check too.

## Limitations that apply to both backends

- **No update, no delete** on the claude.ai MCP side — see
  [`operations.md` — Hard limitation](operations.md#hard-limitation--no-update-no-delete).
  The `oauth_curl` script could in principle update or delete drafts
  too (the Gmail API supports it), but the skills deliberately do
  not, to keep the drafts queue immutable and auditable.
- **Drafts are always drafts** — both backends skip the `send`
  operation. A human review step is non-negotiable.
- **Confidentiality** — both leave drafts in the user's personal
  Gmail account. The `oauth_curl` backend additionally requires the
  user to manage a refresh token on disk; treat it like an SSH key.

## Known issue — thread-attached drafts may not surface in the global Drafts folder when stacked

Caught live on 2026-04-25 during the [`<tracker>#346`](https://github.com/<tracker>/issues/346)
fix-skill flow: when **multiple thread-attached drafts pile up on
the same Gmail thread** within a single skill flow (typical sequence:
security-cve-allocate drafts a CVE-allocated message → security-issue-sync
drafts a corrected version with updated state → security-issue-fix
drafts the final version after a state change), the drafts all carry
the `DRAFT` label in the Gmail API but **only the most recent surfaces
in the user's global Drafts folder in Gmail's UI**. The earlier ones
become reachable only by direct URL or by opening the conversation
view of the thread. The user's own report from that session:
*"Can't see the draft — I see some old drafts on the list but they
are missing"*.

This is a Gmail UI behaviour where multiple thread-attached drafts on
a single conversation collapse / hide in the global Drafts list
rather than rendering as N separate entries. It applies to **both**
backends — `claude_ai_mcp` drafts created with `replyToMessageId` and
`oauth_curl` drafts attached by `threadId` — because both result in
true thread-attached drafts on the Gmail server. The drafts exist
(a Gmail API round-trip confirms `DRAFT` labels and full message
bodies); they are simply not navigable from the standard Drafts
folder when stacked.

The only path that avoids this is creating a draft *without*
attaching it to the inbound thread — the legacy MCP behaviour before
`replyToMessageId` was added. Each such draft becomes its own
top-level entry in the Drafts folder, at the cost of losing
sender-side threading.

### Recommended workflow when re-drafting on a thread that already carries a pending draft

When a skill is about to draft a reply on a thread that **already
has a pending draft on it from an earlier skill pass in the same
session**, omit the thread-attachment parameter for the new draft —
i.e. call `mcp__claude_ai_Gmail__create_draft` *without*
`replyToMessageId` (or `oauth-draft-create` *without* `--thread-id`).
The trade-off:

- **Visibility wins:** the new draft is guaranteed to surface in the
  user's Gmail Drafts folder, so they can actually see and review it.
- **Sender-side threading lost:** the new draft will start a new
  server-side thread on the user's own Gmail. The recipient's mail
  client will still thread it onto the existing conversation via the
  `Re: <exact subject>` match plus the `In-Reply-To` / `References`
  headers Gmail synthesises, so the recipient experience is
  unaffected.

The pile-up case is the only situation where this trade-off applies.
For the **first** draft on a thread, the default thread-attached path
remains preferred — that draft is visible in both the conversation
view and the Drafts folder.

### Concrete steps when the pile-up has already happened

1. **Delete the stale drafts.** `oauth_curl` drafts can be deleted
   via the Gmail API
   (`DELETE https://gmail.googleapis.com/gmail/v1/users/me/drafts/<draft-id>`
   with the OAuth bearer token from the same `oauth_curl` credentials
   file). Drafts created via the claude.ai MCP can only be discarded
   from the Gmail UI (the MCP is no-update / no-delete per
   [`operations.md`](operations.md#hard-limitation--no-update-no-delete)).
2. **Recreate the consolidated message.** Call
   `mcp__claude_ai_Gmail__create_draft` with `replyToMessageId`
   *omitted* and the `Re: <exact subject>` line so the recipient's
   client still threads it via subject match.
3. **Surface the path change in the tracker's status rollup**
   so the audit trail shows why this draft is not thread-attached.
   A future triager looking at the rollup should see *"draft created
   without `replyToMessageId` because the thread already carried a
   pending pile-up"* rather than wondering why the threading
   suddenly degraded.

### When this rule does not apply

- **The thread has no pending draft yet** — keep the default
  thread-attached path (`replyToMessageId` for `claude_ai_mcp`,
  `--thread-id` for `oauth_curl`). The single-draft case does not
  trigger the visibility issue.

## Referenced by

- [`operations.md`](operations.md#drafting-backends) — per-backend call
  shape.
- [`threading.md`](threading.md) — per-backend threading guarantees.
- [`tool.md`](tool.md) — top-level Gmail tool overview.
- [`oauth-draft/README.md`](oauth-draft/README.md) — the `oauth_curl`
  setup walkthrough.
