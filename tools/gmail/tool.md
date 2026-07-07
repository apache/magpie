<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tool: Gmail](#tool-gmail)
  - [What this tool provides](#what-this-tool-provides)
  - [Why this is its own tool](#why-this-is-its-own-tool)
  - [When to replace this tool with another](#when-to-replace-this-tool-with-another)
  - [Confidentiality](#confidentiality)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tool: Gmail

This directory documents the **Gmail** tool adapter — the set of
capabilities the skills use when the adopting project declares Gmail
as a backend in its
[mail-source configuration](../mail-source/contract.md).

A project opts into this tool by listing it in its manifest under
*Mail sources*. For the adopting project see
[`../../<project-config>/project.md`](../../<project-config>/project.md#mail-sources).

Gmail's full capability set per the
[backend contract](../mail-source/contract.md#capability-matrix):
`list_recent_threads`, `read_thread`, `list_drafts`, `list_sent_since`,
`create_draft`, `thread_url`. It is therefore the only in-tree
adapter that supports drafting; an adopter that designates a
read-only primary (e.g. Ponymail, mbox) typically also lists Gmail
as `preferred for create_draft, list_drafts`.

## What this tool provides

The skills use Gmail for four capabilities. Each has its own reference
file in this directory:

| Capability | File | What it covers |
|---|---|---|
| MCP operations | [`operations.md`](operations.md) | The `mcp__claude_ai_Gmail__*` tool catalogue (search, read, draft, list) + the no-update / no-delete limitation |
| Drafting backends | [`draft-backends.md`](draft-backends.md) | The two drafting backends (OAuth + `curl` — **strongly preferred**, preserves URLs verbatim; claude.ai Gmail MCP — **discouraged**: silently rewrites embedded URLs into Google tracking redirects), why `oauth_curl` is preferred, and the `tools.gmail.draft_backend` config knob |
| Threading | [`threading.md`](threading.md) | The *"always attach the draft to the inbound thread when possible"* rule — how drafts stay on the inbound thread across reporter replies, ASF-security relays, PMC credit questions, follow-ups |
| ASF-security-relay drafting | [`asf-relay.md`](asf-relay.md) | Special-case drafting rules when the inbound report is relayed by the ASF security team rather than sent by the external reporter directly |
| Search queries | [`search-queries.md`](search-queries.md) | Gmail search-operator cheat-sheet + skill-specific query templates (candidate-listing, reporter-thread lookup, CVE-review comments) |

Related, adjacent tool:

| Capability | File | What it covers |
|---|---|---|
| ASF PonyMail archive lookups | [`ponymail-archive.md`](ponymail-archive.md) | URL-construction pattern for the ASF's `lists.apache.org` archive (used by `security-issue-sync` to scan the public `users@` archive for the advisory URL, and by `security-issue-import` to resolve a pastable thread URL for the private `security@` list) |

## Why this is its own tool

Gmail is the security team's **inbox** for the private
`security@<project>.apache.org` mailing list and the **draft queue**
for every outbound reporter reply the skills compose. Gmail's draft
capability is load-bearing and cannot be swapped — this directory
stays in every project's toolchain because PonyMail MCP, the
alternative read path documented at
[`../ponymail/tool.md`](../ponymail/tool.md), is read-only and
cannot compose reporter replies.

**Role when PonyMail MCP is opted into.** When a user sets
`tools.ponymail.enabled: true` in their
`.apache-magpie-overrides/user.md` and authenticates the
MCP, PonyMail becomes the primary read backend for archive
queries (reporter-thread lookups, reviewer-comment searches,
`users@` / `dev@` archive scans, prior-rejection precedents).
Gmail stays as the fallback read path — used when a specific list
is outside the user's `tools.ponymail.private_lists` allowlist,
when PonyMail returns an error, or when inbox latency matters
for just-arrived messages. Gmail remains the **only** backend for
draft composition regardless. When the user has not opted into
PonyMail MCP, Gmail is the sole read backend and the skills run
exactly as before.

## When to replace this tool with another

A project that runs on a different mail stack can swap this directory
for a sibling `tools/<name>/` that provides equivalent capabilities
against its own backend (Fastmail, Microsoft Graph, Mailgun, a
`ponymail-mcp` OAuth flow, …). The contract the generic skills rely
on is:

1. **Search** — given a query and a time window, return matching
   thread IDs.
2. **Read** — given a thread ID, return the full message history.
3. **Draft** — given a thread ID, create an unsent reply on the
   inbound thread with thread attachment (the default
   `claude_ai_mcp` backend resolves the thread's latest message ID
   and attaches via `replyToMessageId`; the opt-in `oauth_curl`
   backend attaches by `threadId`); fall back to a subject-matched
   draft (`Re: <root subject>` + `In-Reply-To` / `References`
   headers so the recipient's client still threads it) when the
   thread cannot be resolved. The two backends available today are
   documented in [`draft-backends.md`](draft-backends.md).
4. **List drafts** — so stale drafts can be detected before the
   skills forward-flag them in every new sync comment.

The threading semantics — *"attach the draft to the inbound thread
when possible; fall back to same-subject matching when not, never
fabricate a new subject"* — are non-negotiable regardless of
backend; see [`threading.md`](threading.md).

## Confidentiality

Gmail drafts created by the skills land in the user's personal Gmail
account and are visible only to that user until sent. **Never send** —
the skills only *create* drafts; a human review-and-send step is
required for every outbound message. Confidentiality rules in
[`../../AGENTS.md`](../../AGENTS.md) still bind the draft content:
status updates to the reporter may reference the private tracker URL
(reporter is on the private thread), but any message destined for a
mailing list outside the security circle must be scrubbed.
