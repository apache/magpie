<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`tools/mail-patch/`](#toolsmail-patch)
  - [Prerequisites](#prerequisites)
  - [What this maps](#what-this-maps)
  - [Operations](#operations)
    - [Attribution](#attribution)
    - [Diff identity across backends](#diff-identity-across-backends)
  - [Configuration](#configuration)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/mail-patch/`

**Capability:** contract:change-request

**Kind:** implementation

**Vendor:** email

**Organization:** ASF

`[PATCH]`-mail change-request adapter — the backend that lets a
project driving code review over its **developer mailing list** use
the `pr-management-*` skills. It implements the
[`tools/change-request/`](../change-request/) contract for the oldest
review mechanism in open source: a patch posted to `dev@` as a
`[PATCH]` thread, discussed in replies, and committed to trunk by a
committer.

There is no forge behind this backend at all. The "pull request" is a
mail thread; the "diff" is the `[PATCH]` body or attachment; the
"review" is the reply chain. This adapter composes two contracts the
framework already ships:

- **Reads** flow through [`contract:mail-archive`](../mail-archive/)
  (`tools/ponymail/` at the ASF) — thread search, thread fetch,
  participant extraction.
- **Review replies** are drafted through
  [`contract:mail-create`](../gmail/) — the adapter never sends mail
  autonomously; `post_review` and `reject` produce a drafted reply the
  maintainer sends by hand.

Its `land` verb, like `jira-patch`, delegates the actual commit to the
project's [`contract:source-control`](../asf-svn/) adapter
(`svn patch` + `svn commit`) and then drafts an "applied in rNNNNN"
reply on the thread.

## Prerequisites

- **Runtime:** Bash — doc-only adapter; composes the `mail-archive`,
  `mail-create`, and `source-control` adapters, no local package.
- **CLIs:** the mail-archive backend (PonyMail MCP at the ASF), the
  mail-create backend (Gmail draft API), and `svn` for the delegated
  `land`.
- **Credentials / auth:** anonymous read for public `dev@` archives
  (PonyMail); an authenticated mail-create session to compose replies
  (drafts only — never sends); and ASF committer credentials for the
  SVN commit that `land` delegates to `tools/asf-svn/`. As with
  `jira-patch`, the commit runs under the landing committer's identity
  and credits the patch author in the commit message — see
  [Attribution](#attribution).
- **Network:** the mail archive host (`lists.apache.org`) and
  `svn.apache.org` for the delegated land.

## What this maps

The mail-patch backend resolves the change-request as: **a `[PATCH]`
thread on the developer list is one change proposal.** The thread's
opaque archive id is the proposal `id`; the `[PATCH]` body/attachment
is the diff; the reply chain is the review discussion. A follow-up
`[PATCH v2]` thread is a `superseded`-then-new proposal.

## Operations

Each change-request verb resolves onto the mail surfaces as follows.

| Verb | mail-patch resolution |
|---|---|
| `list_open(filter)` | `mail-archive.list_recent_threads(dev-list, since)` filtered to `[PATCH]`-subject threads that have no terminal "applied"/"rejected" reply. One `proposal_summary` per open patch thread. |
| `get(id)` | `mail-archive.fetch_thread_by_url(id)`; the `diff` is extracted from the first message's `[PATCH]` body or `.patch` attachment. `base` is the trunk from config; `commits` is `[]`; `mergeable` is `unknown` until an `svn patch --dry-run`. |
| `get_discussion(id)` | The thread's reply chain, normalised to `{author, date, body, kind}`. A reply containing the configured approval token (`LGTM` / `+1`) maps to `kind: approval`. |
| `post_review(id, verdict, body)` | **Drafts** a threaded reply via `contract:mail-create` (`in-reply-to` the thread), never sends. The `verdict` shapes the reply's opening line (`+1`, `needs work`); the maintainer reviews and sends. |
| `land(id, strategy)` | **Delegates to `contract:source-control`.** Extracts the patch via `get`, calls the source-control adapter's apply + commit (`svn patch <file>` then `svn commit` — see [`tools/asf-svn/source-control.md`](../asf-svn/source-control.md)), then drafts an "applied in rNNNNN, thanks!" reply on the thread. `strategy` is advisory — SVN lands a patch as one commit (`squash`). |
| `reject(id, reason)` | Drafts a threaded reply carrying `reason`. **No commit** — the absence of a `land` is the rejection. Nothing is transitioned; the thread simply closes socially. |
| `status(id)` | `checks: none` (a mail thread has no CI), `mergeable` from an `svn patch --dry-run`. Skills degrade the `checks` gate to advisory and fall back to a human-judgement prompt (the contract's `status` graceful-degradation path — this is the maximally-degraded backend). |

### Attribution

The delegated `land` credits the patch author in the SVN commit
message (`Patch by <From: header>.`) while committing under the
landing committer's identity — the same convention ASF committers
follow when applying a mailed patch by hand. The adapter reads the
author from the `[PATCH]` message's `From:` header; it never
impersonates the author's identity. This answers #669's
*"patch-author vs. committer attribution"* open question for the
mail-patch backend.

### Diff identity across backends

A `[PATCH]` body has no forge-assigned id, so the adapter derives a
stable proposal id from the thread's archive permalink (the
`mail-archive` thread hash). Re-posted `[PATCH v2]` threads get a new
id and mark the prior thread `superseded` — this is the mail-patch
answer to #669's *"diff identity normalization across backends"* open
question: identity is the *thread*, not the diff bytes.

## Configuration

Declared under the change-request block in
`projects/<project>/project.md`:

```yaml
change_request:
  backend: mail-patch
  land_via: source-control        # land delegates to the VCS adapter
  review_channel: mailing-list
  default_strategy: squash        # SVN applies a patch as one commit
  mail_patch:
    dev_list: dev@<project>.apache.org
    patch_subject_prefix: "[PATCH]"
    approval_token: "LGTM"        # reply token that counts as an approval
    trunk_url: https://svn.apache.org/repos/asf/<project>/trunk
```

- **`dev_list`** — the list `list_open` scans and replies draft against.
- **`patch_subject_prefix`** — the subject marker that identifies a
  patch thread (some projects use `[PATCH]`, some `[PROPOSAL]`).
- **`approval_token`** — the reply string `get_discussion` reads as a
  `kind: approval`.
- **`trunk_url`** — the SVN trunk the delegated `land` applies to.

Backend-specific keys live under `change_request.mail_patch.*`; the
generic keys are the contract's.

## Cross-references

- Contract: [`tools/change-request/`](../change-request/)
- Archive reads: [`tools/mail-archive/`](../mail-archive/) (ASF: [`tools/ponymail/`](../ponymail/))
- Reply drafting: [`contract:mail-create`](../gmail/)
- Delegated land: [`tools/asf-svn/source-control.md`](../asf-svn/source-control.md)
- Issue: [#669](https://github.com/apache/magpie/issues/669)
