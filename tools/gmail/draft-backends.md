<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gmail drafting backends](#gmail-drafting-backends)
  - [Privacy warning — the claude.ai Gmail MCP rewrites embedded URLs into Google tracking redirects](#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)
  - [Why `oauth_curl` is the preferred backend](#why-oauth_curl-is-the-preferred-backend)
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
| OAuth + `curl` script | `oauth_curl` (**strongly preferred — use this**) | **yes** — via `threadId` (and explicit `In-Reply-To` / `References` headers) | one-time Google OAuth client + refresh-token setup, automated via `uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-setup` — see [`oauth-draft/README.md`](oauth-draft/README.md) |
| claude.ai Gmail MCP | `claude_ai_mcp` (**discouraged — do not use; see privacy warning**) | **yes** — via `replyToMessageId` (a message ID resolved from the inbound thread) | none — works as soon as the Gmail connector is authenticated on claude.ai, **but silently rewrites embedded URLs into Google tracking redirects (see below)** |

Both backends create **drafts** — never send. The human review-and-send
step is still required before any outbound message leaves the user's
Gmail.

## Privacy warning — the claude.ai Gmail MCP rewrites embedded URLs into Google tracking redirects

> **Use `oauth_curl`. Do not use the claude.ai Gmail MCP `create_draft`
> for any draft whose body contains URLs.**

As of **2026-06-05**, the claude.ai Gmail MCP `create_draft` tool
**silently rewrites every bare URL in the draft body** into a Google
tracking-redirect wrapper of the form:

```text
https://www.google.com/url?q=<original-url>&source=gmail&ust=<timestamp>&sa=E
```

The rewrite is **baked into the stored draft MIME** — both the
`text/plain` and `text/html` parts — not merely a display artifact
(confirmed by reading the draft back via `drafts.get?format=raw`). So
when the message is sent, the recipient receives the Google redirect
instead of the link the skill wrote. This is unacceptable for the
project's correspondence:

- **Privacy / tracking.** Every link the recipient clicks is routed
  first through `google.com/url`, leaking click metadata (which
  recipient, which link, when) to a third party — on security-sensitive
  correspondence the project has no business funnelling through
  Google's redirector.
- **Reporter-facing and relay correctness.** Many drafts carry a
  reporter-voice **paste-ready block** (e.g. an ASF-security relay the
  recipient pastes onto a GHSA advisory). The rewrite would paste a
  `google.com/url?q=...` redirect onto a public advisory instead of the
  clean canonical URL.
- **Integrity of CVE / advisory links.** Advisory URLs, CVE-record
  URLs, and PR links must reach recipients verbatim; a wrapped link is
  wrong on its face and erodes trust in the message.

The `oauth_curl` backend builds the message with a plain RFC822
`EmailMessage`, so **URLs are preserved verbatim** — no rewriting, no
third-party redirector. That is the decisive reason `oauth_curl` is the
preferred backend for **all** drafting, not just the threadId / bulk
cases.

If `oauth_curl` credentials are genuinely unavailable and a draft must
be created via the MCP, the body **must not contain URLs** — inline the
relevant text and tell the user to add the links by hand before
sending, or (better) set up `oauth_curl` first.

## Why `oauth_curl` is the preferred backend

The `oauth_curl` script talks directly to the Gmail REST API on a
user-provided OAuth refresh token and builds its own MIME, which gives
it three advantages over the claude.ai Gmail MCP:

- **Verbatim URLs (the decisive one)** — it does not rewrite links into
  Google tracking redirects; see the privacy warning above.
- **`threadId`-keyed draft creation** — attaches by `threadId`
  directly; for a brand-new, non-reply message, omit `--thread-id` and
  pass `--no-reply-headers`.
- **Bulk read/modify + delete** — `oauth-draft-mark-read`
  (label-modify on a query result set) has no MCP equivalent, and
  `oauth_curl` is the only backend that can delete drafts via the
  Gmail API.

The one-time cost is a Google OAuth client + refresh-token setup
(automated via `oauth-draft-setup`; see
[`oauth-draft/README.md`](oauth-draft/README.md)). Treat the
credentials file like an SSH key. It is worth it: `oauth_curl` is the
only backend that keeps the project's outbound links clean and
untracked.

## How the skills pick a backend

Every skill step that says *"create a Gmail draft via
`mcp__claude_ai_Gmail__create_draft`"* is shorthand for *"create a draft
via the project's configured drafting backend"* — which should be
`oauth_curl`.

**Preferred — `oauth_curl`.** Resolution:

1. **Probe for `oauth_curl` credentials** in this order:
   - `tools.gmail.oauth_credentials_path` from
     `.apache-magpie-overrides/user.md` when set;
   - the `$GMAIL_OAUTH_CREDENTIALS` environment variable;
   - the default path `~/.config/apache-magpie/gmail-oauth.json`.

   The probe is a single `test -f <path>`.
2. **Create the draft.** Invoke
   `uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-create`
   with `--to`, `--cc`, `--subject`, `--body-file`, and either
   `--thread-id <threadId>` (reply on an existing thread — the tracker
   stores `threadId` per the *security-thread* body field convention)
   or, for a brand-new message, `--no-reply-headers` with no
   `--thread-id`. See [`oauth-draft/README.md`](oauth-draft/README.md)
   for the full shape. URLs in the body are preserved verbatim.

**Last-resort fallback — `claude_ai_mcp`, only when `oauth_curl`
credentials are unavailable.** Subject to the hard constraint in the
[privacy warning](#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)
above: **the body must not contain URLs.** When used:

1. **Resolve the latest message ID on the inbound thread** (for
   threading): call `mcp__claude_ai_Gmail__get_thread(threadId=<inbound>,
   messageFormat='MINIMAL')` and take the `id` of the
   chronologically-last message.
2. **Create the draft** with
   `mcp__claude_ai_Gmail__create_draft(..., replyToMessageId=<that
   message id>)`, or omit `replyToMessageId` to fall back to
   subject-matched threading (see
   [`threading.md`](threading.md#fallback--subject-matched-draft-when-replytomessageid-is-unavailable)).
3. **Warn the user** that the MCP backend was used because `oauth_curl`
   credentials were missing, and that any links were omitted / must be
   added by hand. Do not silently swallow the configuration mismatch.

The skills **surface which backend was used** in the proposal / recap
so the user can tell at a glance how the draft is threaded:

> *Draft created via `oauth_curl` (threadId-attached on
> `<thread-id-prefix>...`)*

or, only when credentials were missing:

> *Draft created via `claude_ai_mcp` (URLs omitted per privacy policy —
> `oauth_curl` credentials not found; threaded via
> `<replyToMessageId / subject-matched fallback>`)*

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

- **Plain text only — never HTML.** Both backends produce plain-text
  (`text/plain`) drafts, and must keep doing so. `oauth_curl` builds a
  single `text/plain` part via `EmailMessage.set_content` (its test
  suite asserts the message stays single-part `text/plain` with no
  `text/html` alternative). For `claude_ai_mcp`, this is guaranteed by
  populating only the `body` parameter and **never** `htmlBody` —
  passing `htmlBody` would add a `text/html` part. The project's
  correspondence (security replies, relays, advisory text) is plain
  text by policy; no skill should ever emit an HTML draft.
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
