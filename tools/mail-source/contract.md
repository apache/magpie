<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Mail source — backend contract](#mail-source--backend-contract)
  - [Abstract operations](#abstract-operations)
  - [Capability matrix](#capability-matrix)
  - [Adopter declaration in `<project-config>/project.md`](#adopter-declaration-in-project-configprojectmd)
    - [Role values](#role-values)
    - [Mandatory flag](#mandatory-flag)
  - [Resolution rule — which backend runs an operation?](#resolution-rule--which-backend-runs-an-operation)
  - [Backend implementation contract](#backend-implementation-contract)
  - [What this contract does NOT cover](#what-this-contract-does-not-cover)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Mail source — backend contract

`security-issue-import` (and the mail-touching paths in
`security-issue-sync`, `security-cve-allocate`, `security-issue-triage`)
scan an inbound `<security-list>` for security reports, read threads,
and draft replies. The skills treat every supported source — Gmail,
PonyMail, IMAP, a static mbox snapshot, the next one we plug in —
the **same way**: through the abstract operations defined here. The
adopting project's `<project-config>/project.md → Mail sources`
section declares *which* backends are configured, what *role* each
plays, and which (if any) are *mandatory*.

This file is the single source of truth for *what a backend is
expected to do* and *how the skills choose between configured
backends*. Backend-specific docs —
[`tools/gmail/tool.md`](../gmail/tool.md),
[`tools/ponymail/tool.md`](../ponymail/tool.md),
[`tools/mail-source/imap/README.md`](imap/README.md), and
[`tools/mail-source/mbox/README.md`](mbox/README.md) —
implement this contract.

## Abstract operations

A mail-source backend exposes some subset of these operations.
*Some subset* matters — Ponymail is read-only, an mbox snapshot is
read-only-and-offline, and a corporate IMAP may or may not allow
drafts depending on policy. The skills check capability before
dispatch; backends that don't support an op are skipped in the
resolution chain for that op.

| Operation | What it does | Why the skills need it |
|---|---|---|
| `list_recent_threads(list, since)` | Return threads on `<list>` newer than `since` (typically 14 / 30 / 90 days) | `security-issue-import` Step 1 — find candidate reports that have arrived since the last sweep |
| `read_thread(thread_id)` | Return full message history of a thread by stable identifier | Steps 2–4 of `-import`; `-sync` reads tracker-linked threads for credit / CVE-reviewer / status signals |
| `list_drafts(thread_id)` | Return draft replies already attached to a thread | Idempotency — never propose a fresh draft when one is already pending |
| `list_sent_since(thread_id, since)` | Return outbound replies sent on a thread within a window | Detect "we already replied; the ball is in the reporter's court" |
| `create_draft(thread_id, body, …)` | Compose an *un-sent* reply attached to the thread (subject inherits, `In-Reply-To` set per the threading rule) | Every reporter-facing reply the skills propose. **Drafts only — never sends** per the framework rule |
| `thread_url(thread_id)` | Return a human-clickable URL to the thread (for tracker body fields, sync rollups, etc.) | The *Security mailing list thread* tracker field |
| `thread_id_kind` (attribute) | The shape of identifiers this backend emits (e.g. Gmail UUID, PonyMail hash, RFC-5322 Message-ID) | Lets the skills tag stored IDs with their source so a future sync from a different backend doesn't dedupe across kinds |

A backend's capability set is its supported subset of the operations
above. The capability matrix below summarises the in-tree adapters.

## Capability matrix

| Backend | `list_recent_threads` | `read_thread` | `list_drafts` | `list_sent_since` | `create_draft` | `thread_url` | Notes |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| [`gmail`](../gmail/tool.md) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Full read + write; primary backend in the reference adopter |
| [`ponymail`](../ponymail/tool.md) | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | Read-only public/private archive viewer; auth via ASF LDAP |
| [`imap`](imap/README.md) | ✓ | ✓ | depends | ✓ | depends | ✓ | Stub adapter; `create_draft` / `list_drafts` depend on whether the IMAP server exposes the Drafts folder writably to the agent |
| [`mbox`](mbox/README.md) | ✓ (offline) | ✓ | ✗ | ✗ | ✗ | ✗ (or `file://`) | Static archive snapshot; forensics / late triage only |

Backends added by adopters extend the matrix in their own adapter
README. The skill never assumes a backend has an op without
consulting the matrix first.

## Adopter declaration in `<project-config>/project.md`

The adopter declares the configured backends under a *Mail sources*
section, one entry per backend:

```markdown
## Mail sources

| Backend | Role | Mandatory | Notes |
|---|---|---|---|
| `gmail`    | primary  | yes | Triager Gmail account is subscribed to `<security-list>` and `<private-list>` |
| `ponymail` | fallback | no  | Read-only archive backstop when Gmail history is incomplete |
```

### Role values

* `primary` — the **default backend** for every operation it
  supports. Exactly one backend may carry this role.
* `preferred for <op>` — overrides `primary` for one specific
  operation. Multiple backends may carry this role, each for a
  different op. Example: a project that runs IMAP for inbound mail
  but uses Gmail only for drafting would declare
  `imap: preferred for read_thread, list_recent_threads` and
  `gmail: preferred for create_draft, list_drafts`.
* `fallback` — try after primary / preferred for any op the
  primary doesn't support, in the order the backends are listed.
* `optional` — available for ad-hoc use but never in the resolution
  chain. Useful for adapter docs that are present but not wired in
  yet.

### Mandatory flag

`yes` means the skill **refuses to run** when the backend is
unavailable (auth missing, MCP server down, archive directory not
mounted). The skill surfaces a clear *"mandatory backend `<name>`
unavailable: `<reason>`; run aborted"* and exits without proposing
anything.

`no` means the skill **continues** with the remaining backends. If a
specific op then has no backend to dispatch to, the skill skips that
operation's proposal (e.g. *"no draft backend available — Step 7
proposal omitted, please draft the receipt-of-confirmation reply by
hand"*) and keeps going.

## Resolution rule — which backend runs an operation?

For each operation `<op>` the skill needs to dispatch:

1. If a backend is marked `preferred for <op>` and the matrix shows
   it supports `<op>` and it is available, use it. **Stop.**
2. Else if the `primary` backend supports `<op>` and is available,
   use it. **Stop.**
3. Else walk the `fallback` backends in the declared order; use the
   first one that supports `<op>` and is available. **Stop.**
4. Else: if any **mandatory** backend was unavailable, abort the
   run per the mandatory rule above. Otherwise skip this
   operation's proposal with a one-line *"no backend available for
   `<op>`"* note and continue.

The resolution result is logged in every proposal recap so the user
can see which backend served which op.

## Backend implementation contract

A new backend (`tools/mail-source/<name>/`) ships a `README.md`
that:

1. States which operations it supports (its column in the matrix
   above).
2. Describes how each supported op is invoked (CLI command, MCP
   tool name, API call) and what identifier shape the backend
   emits for `thread_id`.
3. Documents auth + setup: what credentials / sessions /
   subscriptions the operator needs in place before the skill can
   dispatch.
4. Notes any *fast-path* / *slow-path* differences (e.g. PonyMail's
   private-list reads require an active ASF-LDAP session) so the
   skill can route accordingly.

The contract is intentionally minimal — backends are expected to
gracefully decline ops they don't support (`NotSupported` /
explicit error) rather than fake-implement them. Faking causes
silent data loss (a draft that goes nowhere, a thread read that
returns empty); declining lets the resolution rule fall through.

## What this contract does NOT cover

* **Send semantics.** The framework rule is *draft, never send*;
  every backend that exposes `create_draft` is expected to honour
  it. No backend exposes a `send` op through this contract.
* **PII / privacy filtering.** Backends return raw thread content;
  the privacy-LLM filtering layer (
  [`tools/privacy-llm/`](../privacy-llm/)) sits between the backend
  and any LLM consumer. The contract is at the wire-format level,
  not the content-policy level.
* **Tracker reconciliation.** Backends emit thread IDs and URLs;
  the tracker's *Security mailing list thread* field is owned by
  the tracker, not by any backend. Skills decide what to write
  there based on the resolution result.
