<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Mail-source adapter — IMAP (stub)](#mail-source-adapter--imap-stub)
  - [Capability claim](#capability-claim)
  - [Auth + setup](#auth--setup)
  - [Threading model](#threading-model)
  - [What an adopter declares in `project.md`](#what-an-adopter-declares-in-projectmd)
  - [Why this is a stub](#why-this-is-a-stub)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Mail-source adapter — IMAP (stub)

Reference adapter for a generic IMAP mailbox as a backend for the
`security-issue-import` family of skills. **Stub status** — this
document describes the contract; the concrete CLI / MCP wiring is
TBD and will land when an adopter actually wires IMAP in. The
contract here lets that adopter know *what* they need to provide
without re-deriving it from scratch.

See [`../contract.md`](../contract.md) for the abstract
mail-source-backend operations + capability matrix + adopter
resolution rules this adapter conforms to.

## Capability claim

| Operation | Supported? | Notes |
|---|:---:|---|
| `list_recent_threads(list, since)` | ✓ | `IMAP SEARCH SINCE <date>` against the inbox / `<security-list>` subfolder |
| `read_thread(thread_id)` | ✓ | Fetch all messages whose `References:` / `In-Reply-To:` chain reaches the thread root; thread ID = root Message-ID |
| `list_drafts(thread_id)` | depends | Only if the IMAP server exposes the `Drafts` mailbox writably to the agent's account. Many corporate IMAPs do; many shared role mailboxes don't |
| `list_sent_since(thread_id, since)` | ✓ | `IMAP SEARCH` against the `Sent` mailbox filtering on the thread root's Message-ID in `In-Reply-To:` / `References:` |
| `create_draft(thread_id, body, …)` | depends | Same gating as `list_drafts` — the agent's IMAP account needs `INSERT` rights on the `Drafts` mailbox. Subject and threading headers are set per [`../../gmail/threading.md`](../../gmail/threading.md) (the threading rule is shared across backends) |
| `thread_url(thread_id)` | ✓ (best-effort) | If the project has a public mailing-list archive (PonyMail, Pipermail, hyperkitty), construct the deep-link URL from the Message-ID per the archive's template. If there is no public archive, return a `imap://<host>/<mailbox>;UID=<n>` URL that only works for someone with the same IMAP credentials |
| `thread_id_kind` | `rfc5322-message-id` | RFC-5322 `Message-ID` of the thread root |

## Auth + setup

An adopter wiring IMAP needs to declare:

1. **Server connection** — host, port, TLS preference, server-side
   capabilities the agent will rely on (`IDLE`, `MOVE`, `UIDPLUS`).
2. **Account** — the IMAP user the agent authenticates as. For a
   shared role mailbox (security-triage@example.org) prefer an
   app-password / service-account credential so it can be rotated
   without disrupting individual triagers.
3. **Folder layout** — the inbox path for `<security-list>`, the
   sent path, the drafts path (or `null` to declare the drafts ops
   unsupported).
4. **Credential storage** — where the agent reads credentials from.
   The framework convention is the same shell-env / secret-manager
   pattern other adapters use (see
   [`../../gmail/oauth-draft/README.md`](../../gmail/oauth-draft/README.md)
   as a reference for how a credential lifecycle is documented).

## Threading model

IMAP servers don't have a native "thread" concept — the client
reconstructs threads from `References:` / `In-Reply-To:` chains.
The adapter MUST canonicalise on the **root Message-ID** as the
thread identifier (not the most recent message, not a server-side
folder UID, which can change). This matches the contract's
`thread_id_kind: rfc5322-message-id` so the tracker can store a
stable identifier across reconnects, folder moves, and server
migrations.

## What an adopter declares in `project.md`

```markdown
## Mail sources

| Backend | Role | Mandatory | Notes |
|---|---|---|---|
| `imap` | primary | yes | Subscribed to `security@example.org` via the team mailbox; drafts via Sent-as |
```

…plus an `imap_*` section under *Mail sources* documenting the
host / account / folders / credential path. Use the same shape the
other backends in `<project-config>/project.md` use for their
per-tool config (see the *Gmail and PonyMail* section in the
template for the pattern).

## Why this is a stub

The reference adopter (`airflow-s` / `apache-airflow`) does not
currently use IMAP — Gmail covers the primary path and PonyMail
covers the archive backstop. The stub exists so an adopter that
*does* live on a corporate IMAP (or a self-hosted Postfix +
Dovecot setup) can declare it as the primary backend without
authoring the contract from scratch. When the first adopter wires
it in, the concrete CLI / MCP wiring lands in this directory
alongside this README.
