<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gmail — MCP operation catalogue](#gmail--mcp-operation-catalogue)
  - [Pre-flight](#pre-flight)
  - [Read](#read)
    - [Search threads](#search-threads)
    - [Get thread](#get-thread)
    - [Get the root `Message-ID` of a thread](#get-the-root-message-id-of-a-thread)
  - [Write — drafts only, never send](#write--drafts-only-never-send)
    - [Drafting backends](#drafting-backends)
    - [Create draft — `claude_ai_mcp` backend](#create-draft--claude_ai_mcp-backend)
    - [Create draft — `oauth_curl` backend](#create-draft--oauth_curl-backend)
    - [Hard rules that apply to both backends](#hard-rules-that-apply-to-both-backends)
    - [List drafts](#list-drafts)
    - [Verify-before-claim — never assert a draft is "still pending" without checking](#verify-before-claim--never-assert-a-draft-is-still-pending-without-checking)
  - [Hard limitation — no update, no delete](#hard-limitation--no-update-no-delete)
  - [Confidentiality of drafts](#confidentiality-of-drafts)
  - [Error handling](#error-handling)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gmail — MCP operation catalogue

Shared reference for the `mcp__claude_ai_Gmail__*` tool calls the
skills make against the active user's Gmail account. The skills
reference this file for the call shape and for the limitations that
constrain their flow.

Placeholder convention used below:

- `<security-list>` — the project's private security mailing list (the
  list the user's Gmail account subscribes to). For Airflow, the value
  is `<project manifest>.security_list` =
  `<security-list>`; see
  [`../../<project-config>/project.md`](../../<project-config>/project.md#mailing-lists).
- `<threadId>` — an opaque Gmail thread identifier.

## Pre-flight

Every skill that talks to Gmail does a one-call pre-flight in Step 0
to confirm the MCP is reachable and the user's account subscribes to
the project's security list:

```text
mcp__claude_ai_Gmail__search_threads(
  query='list:<security-list-domain>',
  pageSize=1,
)
```

Substitute the `<security-list-domain>` with the domain suffix of the
project manifest's `security_list` (for
`<security-list>`, the value is
`<security-list-domain>`).

A non-empty result means Gmail is connected and indexed; an empty
result means either the account does not subscribe, or the MCP is
misconfigured. In either case the skill stops and asks the user to
fix the setup rather than guessing.

## Read

### Search threads

```text
mcp__claude_ai_Gmail__search_threads(
  query='<gmail search expression>',
  pageSize=<N>,
)
```

Returns an array of `{threadId, snippet, …}` objects. Use `pageSize`
deliberately — some skills (e.g. `security-issue-sync`) impose a
hard Gmail-call budget per issue to avoid running up the MCP quota
on many-tracker sweeps.

For the search expression syntax and the canonical query templates
the skills use, see [`search-queries.md`](search-queries.md).

### Get thread

```text
mcp__claude_ai_Gmail__get_thread(
  threadId='<threadId>',
  messageFormat='MINIMAL',        # default — see escalation rule below
)
```

**Default to `MINIMAL`.** The `MINIMAL` format returns message
snippets, key headers (`Subject`, `From`, `To`, `Cc`, `Date`), and
message IDs — enough to:

- pick the chronologically-last message for `replyToMessageId`
  attachment;
- detect SENT-by-us vs reporter-replied state on a thread;
- list draft IDs on the thread (`labelIds` carries `DRAFT`);
- check whether the thread exists / has any messages at all;
- read `Subject` for fallback threading when the message ID is lost.

This covers the vast majority of `get_thread` call sites the
skills make. `FULL_CONTENT` returns the entire conversation
including HTML body parts — typically 5-20× the byte size of
`MINIMAL` for a non-trivial thread (a long reporter conversation
can exceed the in-context token limit and spill to disk).

**Escalate to `FULL_CONTENT` only when the call site actually
processes the message body.** Concrete cases that need
`FULL_CONTENT`:

- `security-issue-import` Step 3 — classifies a thread into
  `Report` / `ASF-security relay` / `automated-scanner` / etc.
  by scanning the body for forwarding preambles, credit lines,
  scanner-product tokens.
- `security-issue-sync` Step 1e — extracts CVE-reviewer asks
  from review-comment emails on `<security-list>`.
- Any draft-composition step that quotes the reporter's prior
  message back to them (e.g. when the operator wants to
  reference a specific paragraph the reporter wrote).
- Reading an inbound report's body to extract a credit form
  the reporter explicitly provided (*"please credit me as X"*).

For everything else — thread-state probes, anchor-point
lookups, draft-already-exists checks — default to `MINIMAL`
and avoid the body fetch.

**Cost note.** A 12-tracker bulk sync that calls `get_thread`
once per tracker for state-anchoring lands around
~5K tokens of Gmail context on `MINIMAL`; the same call on
`FULL_CONTENT` typically lands 60-100K tokens. The savings
compound on every bulk run.

**Privacy-LLM contract — apply to every body read.** Every
`get_thread(messageFormat='FULL_CONTENT')` call against a
`<security-list>` thread (or any `<private-list>` thread, where
the approved-LLM gate also applies) MUST be followed by the
redact-after-fetch protocol documented in
[`../privacy-llm/wiring.md`](../privacy-llm/wiring.md#redact-after-fetch-protocol)
before the body is used for any further processing. The window
between `get_thread` returning and `pii-redact` running should
be a single tool invocation wide; the redacted body is what
flows through the rest of the skill. Skills that consume bodies
without running the protocol are framework bugs.

Skip the protocol on `messageFormat='MINIMAL'` calls — the
returned envelope carries the reporter's `From:` header (which
is not redacted under the contract) and routing fields, no
free-form body content. The protocol applies once an actual
body is fetched.

### Get the root `Message-ID` of a thread

> [!IMPORTANT]
> The claude.ai Gmail MCP does **not** expose the RFC-5322
> `Message-ID:` header. The "message IDs" the `get_thread` envelope
> returns are Gmail's *opaque per-message IDs* (the value passed to
> `replyToMessageId`), which only resolve inside the one mailbox that
> holds the thread. The `Message-ID:` header — the archive-independent
> identifier the reporter's MUA stamped, and the value the ASF
> PonyMail archive hashes its permalinks on — is reachable only via
> the Gmail REST API or the PonyMail archive.

`security-issue-import` records the inbound report's root `Message-ID`
in the *Security mailing list thread* tracker field (alongside the
Gmail `threadId` and any PonyMail URL) so the message stays locatable
even from an account that never received the Gmail copy. Resolve it by
backend:

- **PonyMail backend (ASF default primary read path).** The archive
  is keyed on `Message-ID`; `mcp__ponymail__get_email` and
  `mcp__ponymail__search_list` results carry it directly — no extra
  fetch needed.
- **Gmail backend (claude.ai MCP).** Use the `oauth-draft-message-id`
  console script, which reuses the same OAuth credentials as
  `oauth-draft-create` and queries
  `threads.get?format=metadata&metadataHeaders=Message-ID`:

  ```bash
  uv run --project tools/gmail/oauth-draft \
    oauth-draft-message-id <threadId> [<threadId> ...]
  # → one TSV line per thread: <threadId>\t<message-id>
  # → or --json for a {threadId: message-id} object
  ```

  See [`oauth-draft/README.md`](oauth-draft/README.md) for setup. The
  script prints the `Message-ID` of the thread's **root**
  (chronologically first) message — the inbound report. A thread with
  no resolvable header prints an empty value and still exits 0.

When recording the value in a tracker field, **backtick-wrap it** —
a bare `<...@...>` renders as an HTML tag on GitHub and the
identifier vanishes from the rendered issue.

## Write — drafts only, never send

### Drafting backends

Draft creation runs through one of two backends, selected by the user
in `.apache-magpie-overrides/user.md` under
`tools.gmail.draft_backend`. The full comparison and rationale live
in [`draft-backends.md`](draft-backends.md); the call shape per
backend is here.

| Backend | Value | Thread attach? |
|---|---|---|
| OAuth + `curl` | `oauth_curl` (**preferred**) | **yes** — via `threadId` |
| claude.ai Gmail MCP | `claude_ai_mcp` (**discouraged — rewrites URLs; see [`draft-backends.md`](draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)**) | **yes** — via `replyToMessageId` |

### Create draft — `claude_ai_mcp` backend

> **Discouraged.** This backend silently rewrites embedded URLs into
> Google tracking redirects (see
> [`draft-backends.md`](draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)).
> Prefer `oauth_curl`; use this only when `oauth_curl` credentials are
> unavailable AND the body contains no URLs.

The claude.ai Gmail MCP's `create_draft` tool accepts a
`replyToMessageId` parameter (a Gmail *message* ID, not a thread ID).
When supplied, Gmail attaches the draft to the conversation that
contains that message — server-side, on the sender's Gmail. The new
draft is visible in both the conversation view and the global Drafts
folder, and the original message body is appended to the draft's body
(standard "reply" composition). Recipients' mail clients thread-attach
via the subject + `In-Reply-To` / `References` headers Gmail synthesises
from the parent message.

```text
# 1. Resolve the message to reply to. The skills always reply to the
#    chronologically-last message on the inbound thread (see
#    threading.md):
mcp__claude_ai_Gmail__get_thread(
  threadId='<inbound-threadId>',
  messageFormat='MINIMAL',
)
# → take messages[-1].id as <reply-to-message-id>

# 2. Create the draft with replyToMessageId set.
#    Pass `body` (plain text) ONLY — never `htmlBody`. The tool sends
#    a plain-text message iff `htmlBody` is omitted; supplying it adds
#    a text/html alternative, which the project never wants.
mcp__claude_ai_Gmail__create_draft(
  subject='Re: <root subject of the inbound message>',
  to=['<primary>'],
  cc=['<security-list>', ...],
  body='<body>',                # plain text only
  replyToMessageId='<reply-to-message-id>',
  # htmlBody=...                # DO NOT SET — would make the draft HTML
)
```

- **Plain text only — never set `htmlBody`.** The `create_draft` tool
  produces a plain-text message when only `body` is supplied; passing
  `htmlBody` (or `body` + `htmlBody`) creates a `text/html` part. The
  project's outbound mail is always plain text, so only ever populate
  `body`.
- **`replyToMessageId` is the message ID of the latest message on the
  inbound thread.** Resolve it from `get_thread` rather than guessing
  — Gmail does not accept a `threadId` here.
- **Subject is always `Re: <root subject>`**, never fabricated. A
  drifted subject defeats subject-based threading on every client and
  is a separate signal Gmail's UI uses to render the conversation
  header.
- **Never send.** The skills only *create* drafts; a human
  review-and-send step is required before every outbound message.
- **Fallback** — when the inbound `threadId` cannot be resolved or
  the latest message is not retrievable, omit `replyToMessageId` and
  let the draft thread by subject only. See the
  [fallback rule](threading.md#fallback--subject-matched-draft-when-replytomessageid-is-unavailable)
  in `threading.md` for when this applies and when it does not.

### Create draft — `oauth_curl` backend

The `oauth-draft-create` console script (in
[`oauth-draft/`](oauth-draft/README.md)) creates drafts by talking
directly to the Gmail REST API with a user-provided OAuth refresh
token. It sets `threadId` on the Gmail API call **and** populates
`In-Reply-To` / `References` from the thread's last message, so every
client threads consistently.

```bash
uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-create \
  --thread-id <gmail-threadId> \
  --to reporter@example.com \
  --cc <security-list> \
  --subject "Re: <root subject>" \
  --body-file /tmp/body.txt
```

See [`oauth-draft/README.md`](oauth-draft/README.md) for one-time
setup (creating the Google Cloud OAuth client, obtaining a refresh
token, and populating the credentials file) and for the full flag
list.

Every bullet from the `claude_ai_mcp` section above applies to this
backend too — drafts only, never send; subject is always
`Re: <root subject>`; composition happens under user review.

### Hard rules that apply to both backends

- **Never send.**
- **Plain text only — never HTML.** Every draft is a plain-text
  (`text/plain`) message. For `claude_ai_mcp`, populate `body` and
  never `htmlBody`. For `oauth_curl`, the script builds a single
  `text/plain` part via `EmailMessage.set_content` (asserted by its
  test suite). Do not introduce an HTML body in either backend.
- **Subject is always `Re: <root subject>`**, never fabricated.
- **Run `pii-reveal` before passing the body to the create-draft
  call.** If the draft body carries any third-party identifiers
  the skill redacted earlier (e.g. when assembling a CVE-credit
  line referencing a non-reporter, non-collaborator individual),
  the rendered draft text MUST be passed through `pii-reveal`
  *once*, immediately before the create-draft tool call, so the
  recipient sees the real value. Drafts whose bodies contain only
  the reporter's own identity (already not-redacted under the
  contract) need no reveal step. The full reveal-before-send
  protocol is in
  [`../privacy-llm/wiring.md`](../privacy-llm/wiring.md#reveal-before-send-protocol).
- **Surface which backend was used** in the proposal / recap so the
  user can tell at a glance whether the draft threads on their own
  Gmail view (`oauth_curl`) or only on the recipient's
  (`claude_ai_mcp` subject fallback).
- **Record the backend + draft ID on the tracker's status rollup**
  so subsequent sync passes can find and (optionally) re-verify the
  draft.

For the ASF-security-relay special case (different `to` /
`cc` shape), see [`asf-relay.md`](asf-relay.md).

### List drafts

```text
mcp__claude_ai_Gmail__list_drafts(
  query='<optional filter>',    # e.g. 'list:<security-list-domain>'
)
```

Used by `security-issue-sync` to verify that a draft flagged as stale
in a previous status comment still exists before carrying the flag
forward. See the *"self-replicating stale-draft flag"* paragraph in
that skill.

### Verify-before-claim — never assert a draft is "still pending" without checking

Any skill that writes a tracker status comment, proposal, or recap
line of the shape *"Reporter notification still pending — see draft
`<draftId>`"* (or any analogous "draft is awaiting send" claim) MUST
call `list_drafts` immediately before emitting the line and confirm
`<draftId>` is in the returned set.

- **If the `draftId` is in the result** → emit the "still pending"
  line as planned.
- **If the `draftId` is NOT in the result** → the draft is gone:
  the user has either sent it (Gmail moves sent items out of Drafts)
  or discarded it. Do **not** emit "still pending". Instead, flip
  the line to one of:
  - *"Reporter draft `<draftId>` is no longer in Drafts — sent or
    discarded (verify in Sent if uncertain)."* — neutral, no false
    claim.
  - *"Reporter has been notified on the original mail thread."* —
    only if the skill can independently confirm the send (e.g. via
    `list_sent_since` filtered to the recipient, or
    `get_thread(threadId)` showing a SENT message after the draft
    was created).

The rule applies in **every** sync, not only on stale-flag
carry-forward. The "draft was just created in this same pass" case
is no exception — the user may have switched to Gmail and sent it
between the create call and the status-comment post; one extra
`list_drafts` call covers the race.

Without this guard, a "still pending" flag posted on one sync
self-replicates across every subsequent sync long after the user
has actually sent the email, nagging the team about a phantom
pending notification.

## Hard limitation — no update, no delete

The Gmail MCP exposes **`create`, `list`, and `read` only** for
drafts. There is no `update_draft` and no `delete_draft` tool. The
skills must treat every existing draft as immutable:

- If a correction is needed, surface the existing draft's `draftId`
  to the user with an explicit *"discard this one manually in Gmail"*
  note, then create a fresh draft with the corrected content.
- Do **not** silently create a second draft that shadows the first —
  that leaves two near-identical drafts in the user's Gmail and
  invariably one of them gets sent by accident.
- On the sync skill's stale-draft-forward-flagging path: verify the
  `draftId` still exists via `list_drafts` before copying the flag
  into a new sync status comment. Without verification, a one-time
  flag self-replicates forever.

## Confidentiality of drafts

Drafts land in the user's personal Gmail account and are visible only
to that user until sent. Draft content may reference the private
tracker's URL (reporter is on the private thread and is expected to
keep it confidential), but anything destined for a public list must
obey the confidentiality rules in
[`../../AGENTS.md`](../../AGENTS.md) — no `<tracker>` URLs, no CVE
IDs before publication, no *"security fix"* leakage.

## Error handling

If any Gmail call fails (MCP unreachable, 429, transient 5xx),
**stop** and report the failure. The skills explicitly budget Gmail
calls; silently retrying turns one flaky call into a quota-exhaustion
storm.
