<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Mail-source adapter — mbox / local archive](#mail-source-adapter--mbox--local-archive)
  - [When this adapter makes sense](#when-this-adapter-makes-sense)
  - [Capability claim](#capability-claim)
  - [Auth + setup](#auth--setup)
  - [What an adopter declares in `project.md`](#what-an-adopter-declares-in-projectmd)
  - [Why this shipped before its first adopter](#why-this-shipped-before-its-first-adopter)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Mail-source adapter — mbox / local archive

Reference adapter for a static `mbox` (or `Maildir`, or a directory
of `.eml` files) as a read-only backend for the
`security-issue-import` family of skills. **Implemented** — the
concrete reader and its three operations live in
[`tools/maildir/`](../../maildir/README.md#contractmail-source--local-archive-reads),
the vendor home for this local-files backend.

See [`../contract.md`](../contract.md) for the abstract
mail-source-backend operations + capability matrix + adopter
resolution rules this adapter conforms to.

The concrete vendor home for this local-files backend is
[`tools/maildir/`](../../maildir/) (Vendor: `Maildir`). That tool pairs
this inbound read side with a fully-implemented outbound side — it files
editable drafts into a local Maildir for the `contract:mail-create`
capability — so one offline, credential-free vendor covers both mail
directions, the way `tools/gmail` does for Google.

## When this adapter makes sense

* **Forensics / late triage of a historical security thread.** The
  inbox is gone or the role mailbox is no longer credentialed, but
  the messages were archived to an mbox snapshot at the time. The
  skill can still classify, extract template fields, and reconcile
  against trackers — it just can't draft a reply.
* **Air-gapped triage environments.** The agent runs offline against
  a thumbdrive snapshot of `<security-list>` for the time window
  being audited.
* **Compliance / discovery exports.** A regulator request produces
  an mbox export of all `<security-list>` mail for a time range; the
  skill imports it the same way it would import live mail, into a
  scratch tracker repo, without touching any live mail credentials.

## Capability claim

| Operation | Supported? | Notes |
|---|:---:|---|
| `list_recent_threads(list, since)` | ✓ (offline) | Parse the mbox, group messages under the thread root the `References:` / `In-Reply-To:` chain names (first ID wins, whether or not that message is in the archive), filter by message `Date:` newer than `since`. The `list` parameter is *advisory* — the mbox is whatever the operator pointed the adapter at, no remote subscription is checked |
| `read_thread(thread_id)` | ✓ | Same parser; return all messages in the thread |
| `list_drafts(thread_id)` | ✗ | A static archive has no concept of pending drafts |
| `list_sent_since(thread_id, since)` | ✗ (or limited) | Only if the archive includes the team's outbound mail (some exports do; many don't). The adapter declares this op as `unsupported` by default; an adopter with an outbound-included archive may upgrade the claim per-deployment |
| `create_draft(thread_id, body, …)` | ✗ | Read-only by construction |
| `thread_url(thread_id)` | depends | If the project has a public archive (PonyMail, Pipermail), construct the URL from the thread root's Message-ID. Otherwise return `file://<archive-path>#<message-id>` which only works in the operator's local environment |
| `thread_id_kind` | `rfc5322-message-id` | Same as IMAP, and in the same bracketed form (`<root@host>`) — the root Message-ID is the stable identifier. A message with no `Message-ID` is keyed by a hash of its bytes instead and reported under the `content-hash` kind |

## Auth + setup

There is no auth — the archive file is a file. The adopter
declares:

1. **Archive path** — absolute path to the mbox file, or to the
   `Maildir/` root, or to a directory of `.eml` files. The adapter
   sniffs format from the path shape.
2. **Time window cap** — optional safety knob to refuse parsing
   archives larger than `N` MB unless explicitly approved. Prevents
   accidental long-running parses of multi-year archives.
3. **Read-only enforcement** — the adapter MUST NOT write to the
   archive path under any circumstance. The framework's
   privacy-LLM gate (see [`../../privacy-llm/`](../../privacy-llm/))
   should also be considered before sending archive content to
   any LLM consumer.

## What an adopter declares in `project.md`

```markdown
## Mail sources

| Backend | Role | Mandatory | Notes |
|---|---|---|---|
| `mbox` | primary | yes | Forensics-only deployment; archive at `/srv/audit/security-list-2024.mbox` |
```

…or as a fallback for an otherwise-live deployment:

```markdown
| `gmail` | primary  | yes | Triager Gmail subscribed to `<security-list>` |
| `mbox`  | fallback | no  | 2024-Q4 snapshot at `/srv/snapshots/security-list-2024-Q4.mbox`; used when Gmail history is incomplete |
```

## Why this shipped before its first adopter

No adopter is using it yet. The contract shape is small and stable
enough — three read operations over a file the adopter already has —
that wiring it now costs less than re-deriving the read interface
from a forensics / compliance team's requirements later. The reader
is deliberately whole-archive and stateless: these are snapshots
measured in tens of megabytes, not live mailboxes, so an index would
be a second thing to keep consistent for no gain.
