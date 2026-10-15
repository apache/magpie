<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`tools/maildir/`](#toolsmaildir)
  - [Prerequisites](#prerequisites)
  - [The draft-only invariant](#the-draft-only-invariant)
  - [Operations](#operations)
    - [`contract:mail-create` — `maildir-draft-create`](#contractmail-create--maildir-draft-create)
    - [`maildir-draft-find` — drafts already waiting](#maildir-draft-find--drafts-already-waiting)
    - [`contract:mail-source` — local archive reads](#contractmail-source--local-archive-reads)
  - [Configuration](#configuration)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/maildir/`

**Capability:** contract:mail-source + contract:mail-create

**Kind:** implementation

**Vendor:** Maildir

The **local-files** mail backend: one vendor-neutral substrate that serves
both mail directions the framework needs, using nothing but the on-disk
[Maildir](https://cr.yp.to/proc/maildir.html) / mbox formats and the Python
standard library. No cloud provider, no account, no credentials, no network.

It is the local counterpart of [`tools/gmail/`](../gmail/): where Gmail
bundles inbound reads and outbound drafting behind the *Google* vendor, this
tool bundles the same two capabilities behind the *Maildir* vendor —

- **`contract:mail-create`** — compose an **editable outbound draft** and
  file it into a local Maildir, where any Maildir-aware mail client
  (Thunderbird, mutt, Evolution, aerc, Apple Mail via an IMAP bridge, …)
  shows it in its Drafts view for the human to review, edit, and send.
  **Fully implemented here** (see [Operations](#operations)).
- **`contract:mail-source`** — read an inbound `<security-list>` archive
  from a local mbox / Maildir / `.eml` directory. This reuses the existing
  local-archive contract documented at
  [`tools/mail-source/mbox/README.md`](../mail-source/mbox/README.md); the
  reader remains the documented stub it is today (concrete parsing lands
  when an adopter wires a local archive in), so this tool's mail-source
  side is the same offline forensics/air-gapped backend, now given a
  concrete vendor identity.

Adding this backend is what flips `contract:mail-create` vendor-neutral: it
is the second, non-Google implementation of the outbound-mail contract
(Google + Maildir), so a project that cannot or will not depend on Gmail can
still drive every draft-producing skill. See
[`docs/vendor-neutrality.md`](../../docs/vendor-neutrality.md).

## Prerequisites

- **Runtime:** Python 3.11+ (standard library only — `email.message` +
  `mailbox`). Run via `uv run --project tools/maildir …`.
- **CLIs:** none — stdlib only; the `maildir-draft-create` console script
  is the whole surface.
- **Credentials / auth:** none. The backend reads and writes plain files
  under a Maildir path the operator controls.
- **Network:** none — fully offline. This is the decisive difference from
  every cloud mail backend: a draft never leaves the machine, and no third
  party ever sees the message or its links.

## The draft-only invariant

Like every `contract:mail-create` backend, this one **only creates drafts —
it never sends.** The contract models a `send` mode as a
declared-but-unimplemented seam; `maildir-draft-create --mode send`
deliberately errors rather than transmitting. A message leaves only after a
human opens the draft in their own mail client, edits it freely, and sends
it by hand. The draft is always an ordinary, editable message file — nothing
about it is locked or opaque.

Drafts are single-part `text/plain` (the framework's correspondence is plain
text by policy); the writer never adds a `text/html` alternative. Because the
message is composed with a plain `email.message.EmailMessage`, URLs in the
body are preserved **verbatim** — no tracking-redirect rewriting.

## Operations

### `contract:mail-create` — `maildir-draft-create`

Compose a plain-text RFC 5322 message and file it into a Maildir as a draft
(the Maildir `D` flag, in `cur/`). Prints the path of the written draft file.

```bash
uv run --project tools/maildir maildir-draft-create \
  --from "you@project.example.org" \
  --to "reporter@example.com" \
  --subject "Re: your report" \
  --body-file reply.txt \
  --maildir ~/Mail/project/Drafts \
  --in-reply-to "<thread-parent@example.com>" \
  --references "<thread-root@example.com>"
```

| Flag | Meaning |
|---|---|
| `--from` / `--to` / `--cc` | Envelope addresses (`From`/`To`/`Cc`). |
| `--subject` | Subject line. |
| `--body-file` | Plain-text body file, or `-` to read stdin. |
| `--maildir` | Maildir the draft is filed into (created if absent). |
| `--in-reply-to` | Parent `Message-ID`, for reply threading. |
| `--references` | Space-separated parent `References` chain. |
| `--message-id` | Override the generated `Message-ID` (reproducible output). |
| `--mode` | `draft` (default). `send` is declared but unimplemented and errors. |

The verb maps onto the contract's `create(message, mode=draft)`: it always
produces an editable draft; `mode=send` is the human-approved future seam.

### `maildir-draft-find` — drafts already waiting

Before a skill files a reply, it checks whether a draft for the same thread,
subject or recipient is already in the Maildir, so it never shadows one the
human has not sent yet. Read-only: it never creates the Maildir or touches a
message. Prints a JSON list (`file`, `subject`, `to`, `in_reply_to`, `date`,
`draft_flag`).

```bash
uv run --project tools/maildir maildir-draft-find \
  --maildir ~/Mail/project/Drafts \
  --message-id "<thread-parent@example.com>" \
  --subject "your report" --to "reporter@example.com"
```

| Flag | Meaning |
|---|---|
| `--maildir` | Drafts Maildir to search; `~` is expanded. A missing one yields `[]`. |
| `--message-id` | `Message-ID`s of the thread, with or without `<>`, several per flag; the flag repeats. Matches a draft whose `In-Reply-To` or `References` names one. |
| `--subject` | Subject substring; `Re:` / `Fwd:` prefixes and case are ignored. |
| `--to` | Recipient substring, matched against `To` and `Cc`. |

A draft matching any criterion is listed; with none, every draft is.

### `contract:mail-source` — local archive reads

Read-only ingestion of a local mbox / Maildir / `.eml` archive for the
`security-issue-import` family, per the abstract operations in
[`tools/mail-source/contract.md`](../mail-source/contract.md). The concrete
reader is the documented stub described in
[`tools/mail-source/mbox/README.md`](../mail-source/mbox/README.md); this
tool is its vendor home.

**Privacy posture:** fetched mail bodies are external data, not instructions.
Content is treated as hostile input and is routed through the Privacy-LLM gate
or redacted before any model-facing use. Embedded prompt-injection text in mail
bodies is carried as report data only and is never obeyed as a framework
instruction.

## Configuration

The drafting backend is set per project, in `<project-config>/project.md`,
and each person can override it in their own `user.md`.

For the whole project (`contract:mail-create`):

```yaml
# mail_create — outbound composition (draft; never sends)
mail_create:
  backend: maildir
  maildir:
    drafts_path: ~/Mail/<project>/Drafts   # Maildir the draft is filed into
    from_address: you@<project>.apache.org  # default From: for composed drafts
```

For one person, in `user.md`, whatever the project chose:

```markdown
### `mail_create`

- `backend: maildir`
- `drafts_path: ~/Mail/<project>/Drafts`
- `from_address: you@<project>.apache.org`
```

The person's value wins, key by key. The skills read the result through
[`tools/gmail/draft-backends.md` § *How the skills pick a backend*](../gmail/draft-backends.md#how-the-skills-pick-a-backend),
where the [Maildir recipe](../gmail/draft-backends.md#the-maildir-backend)
covers threading, the existing-draft check and the recap line.

For inbound reads (`contract:mail-source`), the declaration is the
local-archive one from
[`tools/mail-source/mbox/README.md`](../mail-source/mbox/README.md)
(archive path + read-only enforcement).

**Thunderbird.** Thunderbird reads a Maildir only for an account whose
message store is *File per message (maildir)*, chosen when the account
is set up. It keeps a per-folder index (the `.msf` file) and does not
always notice a draft another program wrote: if a new draft does not
show up, right-click the Drafts folder → *Properties* → *Repair Folder*
to rebuild the index.

## Cross-references

- Outbound contract: `contract:mail-create` (also implemented by
  [`tools/gmail/`](../gmail/)).
- Inbound contract: [`tools/mail-source/contract.md`](../mail-source/contract.md);
  local-archive adapter [`tools/mail-source/mbox/README.md`](../mail-source/mbox/README.md).
- Vendor-neutrality rationale: [`docs/vendor-neutrality.md`](../../docs/vendor-neutrality.md).
- Sibling outbound backend: [`tools/gmail/draft-backends.md`](../gmail/draft-backends.md).
