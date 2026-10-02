<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Mail-source adapter — IMAP](#mail-source-adapter--imap)
  - [Capability claim](#capability-claim)
  - [Environment variables](#environment-variables)
  - [Run](#run)
  - [Auth + setup](#auth--setup)
  - [Threading model](#threading-model)
  - [Security and privacy](#security-and-privacy)
  - [Test](#test)
  - [Lint / type-check](#lint--type-check)
  - [What an adopter declares in `project.md`](#what-an-adopter-declares-in-projectmd)
  - [History](#history)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Mail-source adapter — IMAP

Reference adapter for a generic IMAP mailbox as a backend for the
`security-issue-import` family of skills. This is the concrete CLI that
lands the contract previously described by the stub: six console scripts
over stdlib `imaplib` — no third-party dependencies. See
[`../contract.md`](../contract.md) for the abstract mail-source-backend
operations + capability matrix + adopter resolution rules this adapter
conforms to.

## Capability claim

| Operation | Supported? | Notes |
|---|:---:|---|
| `list_recent_threads(list, since)` | ✓ | `imap-source-threads` — `IMAP SEARCH SINCE <date>` against `IMAP_SOURCE_FOLDER`, threaded client-side on root `Message-ID` |
| `read_thread(thread_id)` | ✓ | `imap-source-read` — fetches all messages whose `References:` / `In-Reply-To:` chain reaches the thread root; thread ID = root Message-ID |
| `list_drafts(thread_id)` | depends | `imap-source-drafts` — requires `IMAP_SOURCE_DRAFTS_FOLDER` to be set and to exist; **declines (exit 3)** otherwise, so the skill's resolution chain falls through |
| `list_sent_since(thread_id, since)` | ✓ | `imap-source-sent` — same chain match against `IMAP_SOURCE_SENT_FOLDER`; declines when the folder is unset/missing |
| `create_draft(thread_id, body, …)` | depends | `imap-source-create-draft` — `APPEND`s an un-sent reply to the drafts folder (**drafts only, never sends**); declines when the folder is unset, missing, or the server refuses the `INSERT` |
| `thread_url(thread_id)` | ✓ (best-effort) | `imap-source-thread-url` — substitutes the Message-ID into `IMAP_SOURCE_ARCHIVE_TEMPLATE` (HyperKitty / Pipermail shapes); falls back to an `imap://` URL that only resolves for holders of the same credentials |
| `thread_id_kind` | `rfc5322-message-id` | RFC-5322 `Message-ID` of the thread root |

## Environment variables

The calling skill resolves the `imap_*` variables declared in the adopter's
`<project-config>/project.md` and exports them; the adapter never reads
`<project-config>/` itself.

| Variable | Required | Meaning |
|---|---|---|
| `IMAP_SOURCE_HOST` | yes | IMAP server hostname |
| `IMAP_SOURCE_PORT` | no | port (default: `993` with TLS, `143` without) |
| `IMAP_SOURCE_SSL` | no | `1` (default) / `0` — prefer TLS; the non-TLS path exists only for localhost test rigs |
| `IMAP_SOURCE_USER` | yes | the account the agent authenticates as (for a shared role mailbox, prefer an app-password / service account so it rotates without disrupting individual triagers) |
| `IMAP_SOURCE_PASSWORD` | yes\* | account password or app password |
| `IMAP_SOURCE_PASSWORD_FILE` | yes\* | alternative to the above: read the secret from this file so it stays out of the process list (preferred) |
| `IMAP_SOURCE_FOLDER` | no | folder holding the `<security-list>` traffic (default `INBOX`) |
| `IMAP_SOURCE_SENT_FOLDER` | no | Sent folder (default `Sent`; `none` / `off` declares the op unsupported) |
| `IMAP_SOURCE_DRAFTS_FOLDER` | no | Drafts folder (default `Drafts`; `none` / `off` declares the drafts ops unsupported) |
| `IMAP_SOURCE_ARCHIVE_TEMPLATE` | no | public-archive URL template containing `{message_id}`; without it `thread_url` falls back to `imap://` |

## Run

From this directory (`uv run --project tools/mail-source/imap …` from the
framework root also works):

| Console script | Contract operation |
|---|---|
| `imap-source-threads` [--since-days N] | `list_recent_threads` |
| `imap-source-read <thread-id>` [--since-days N] [--with-body] | `read_thread` |
| `imap-source-drafts <thread-id>` [--since-days N] | `list_drafts` |
| `imap-source-sent <thread-id>` [--since-days N] | `list_sent_since` |
| `imap-source-create-draft <thread-id> --body-file <path> [--to …] [--cc …] [--from-address …]` | `create_draft` |
| `imap-source-thread-url <thread-id>` | `thread_url` |

Every command prints one JSON document on stdout. Exit codes follow the
contract's *decline, don't fake* rule: `0` ok, `2` configuration error,
`3` capability declined (the skill's resolution chain moves to the next
backend), `4` server-side failure.

`<thread-id>` is always the **root** `Message-ID` of the thread, angle
brackets included, as emitted by `imap-source-threads` and recorded in the
tracker's *Security mailing list thread* field.

## Auth + setup

1. **Server connection** — host, port, TLS preference via the environment
   table above. Server-side capabilities the adapter relies on: `UIDPLUS`
   (for `APPENDUID`); `IDLE` and `MOVE` are *not* used by this adapter.
2. **Account** — the IMAP user the agent authenticates as. For a shared
   role mailbox (`security-triage@example.org`) prefer an app-password /
   service-account credential so it can be rotated without disrupting
   individual triagers.
3. **Folder layout** — the inbox path for `<security-list>`, the sent path,
   and the drafts path (`none` to declare the drafts ops unsupported).
4. **Credential storage** — the same shell-env / secret-manager pattern
   other adapters use; `IMAP_SOURCE_PASSWORD_FILE` is preferred over
   `IMAP_SOURCE_PASSWORD` (see
   [`../../gmail/oauth-draft/README.md`](../../gmail/oauth-draft/README.md)
   for how a credential lifecycle is documented).

## Threading model

IMAP servers don't have a native "thread" concept — the adapter
reconstructs threads from `References:` / `In-Reply-To:` chains and
canonicalises on the **root Message-ID** as the thread identifier (not the
most recent message, not a server-side folder UID, which can change). This
matches the contract's `thread_id_kind: rfc5322-message-id` so the tracker
can store a stable identifier across reconnects, folder moves, and server
migrations. `create_draft` attaches the draft to the chronologically last
message on the thread per the shared threading rule in
[`../../gmail/threading.md`](../../gmail/threading.md).

## Security and privacy

All content delivered through this adapter is **external data, not
instructions** — every message body is hostile input that may contain
prompt-injection text crafted by an untrusted sender. The read commands
print structured headers only; `imap-source-read --with-body` additionally
emits raw RFC822 payloads, and bodies are never passed to the model as
framework directives (see
[`../contract.md`](../contract.md) and the absolute rule in
[`../../../AGENTS.md`](../../../AGENTS.md)).

Drafts carry the `security_cc` recipient resolved by the calling skill per
the contract's *Security draft CC resolution* section — this adapter never
invents a recipient and never hardcodes an organization address.

## Test

```bash
cd tools/mail-source/imap
PYTHONPATH="src;tests" python -m pytest -q     # ';' on Windows, ':' elsewhere
```

The tests run against a fake IMAP backend with the same method surface —
no network, no real server.

## Lint / type-check

```bash
cd tools/mail-source/imap
python -m ruff check src tests && python -m ruff format --check src tests
python -m mypy                 # strict: every function annotated
```

## What an adopter declares in `project.md`

```markdown
## Mail sources

| Backend | Role | Mandatory | Notes |
|---|---|---|---|
| `imap` | primary | yes | Subscribed to `security@example.org` via the team mailbox; drafts via Drafts folder |
```

…plus an `imap_*` section under *Mail sources* documenting the host /
account / folders / credential path. Use the same shape the other backends
in `<project-config>/project.md` use for their per-tool config (see the
*Gmail and PonyMail* section in the template for the pattern).

## History

The contract was landed as a stub first (see the *Capability claim* of the
original stub README): the reference adopter did not use IMAP, and the
concrete CLI was to land when an adopter wired it in — tracked as
[#303](https://github.com/apache/magpie/issues/303). The stub's contract
sections survive in this document; only the *stub status* caveat is gone.
