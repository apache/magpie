<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [oauth-draft](#oauth-draft)
  - [Run](#run)
  - [Setup — one-time](#setup--one-time)
  - [How threading is guaranteed](#how-threading-is-guaranteed)
  - [Confidentiality](#confidentiality)
  - [Test](#test)
  - [Lint / type-check](#lint--type-check)
  - [Referenced by](#referenced-by)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- Licensed to the Apache Software Foundation (ASF) under one
     or more contributor license agreements.  See the NOTICE file
     distributed with this work for additional information
     regarding copyright ownership.  The ASF licenses this file
     to you under the Apache License, Version 2.0 (the
     "License"); you may not use this file except in compliance
     with the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

     Unless required by applicable law or agreed to in writing,
     software distributed under the License is distributed on an
     "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
     KIND, either express or implied.  See the License for the
     specific language governing permissions and limitations
     under the License. -->

# oauth-draft

Small Python project that talks directly to the Gmail REST API on a
user-provided OAuth refresh token. Four console scripts:

| Console script | Purpose |
|---|---|
| `oauth-draft-setup` | One-time interactive OAuth consent flow that writes the credentials JSON. |
| `oauth-draft-create` | Create a Gmail draft with `threadId` attachment. (As of the `replyToMessageId` parameter on the claude.ai Gmail MCP `create_draft`, the MCP can also produce thread-attached drafts — see [`../draft-backends.md`](../draft-backends.md). This script remains useful when you have a `threadId` on hand and would rather skip the extra `get_thread` round-trip the MCP path requires, and is the only path that lets the skills delete drafts via the Gmail API afterwards.) |
| `oauth-draft-mark-read` | Bulk-modify Gmail threads matching a search query (default: mark as read by removing the `UNREAD` label). No MCP equivalent today. |
| `oauth-draft-message-id` | Resolve the root RFC-5322 `Message-ID` header of one or more threads (`threads.get?format=metadata`). No MCP equivalent — the claude.ai Gmail MCP `get_thread` surfaces only Gmail's opaque per-message IDs, never the `Message-ID:` header. `security-issue-import` records the result in the *Security mailing list thread* tracker field. |

The **strongly preferred** drafting backend is this `oauth_curl` tool:
the claude.ai Gmail MCP `create_draft` silently rewrites embedded URLs
into Google tracking redirects, so it must not be used for drafts that
contain links — see
[`../draft-backends.md`](../draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects).
This README covers local-setup, day-to-day invocation, and the
project's own test/lint workflow.

## Run

From the framework's root (this repository when running standalone;
the `.apache-magpie/` snapshot path inside an adopting tracker repo):

```bash
uv run --project tools/gmail/oauth-draft oauth-draft-create \
  --thread-id <gmail-threadId> \
  --to reporter@example.com \
  --cc security@<project>.apache.org \
  --subject "Re: <root subject>" \
  --body-file /path/to/body.txt
```

Skill files and framework docs reference the same invocation via the
`<framework>` placeholder so the path resolves in either context:

```bash
uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-create ...
```

`<framework>` substitutes to `.apache-magpie/apache-magpie` in
adopting projects and to `.` (the repository root) in framework
standalone — see the placeholder convention in
[`AGENTS.md`](../../../AGENTS.md#placeholder-convention-used-in-skill-files).

The other two scripts follow the same shape:

```bash
# Bulk mark-as-read (dry-run by default; add --execute to actually modify)
uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-mark-read \
  --query 'label:apache-security in:spam is:unread'

# Add --execute after reviewing the dry-run output
uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-mark-read \
  --query 'label:apache-security in:spam is:unread' --execute

# Resolve the root Message-ID of one or more threads (TSV, or --json)
uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-message-id \
  19e9d09a31ff6bdd 19dda947a5d6ca88
```

Per-flag help: `oauth-draft-create --help`,
`oauth-draft-mark-read --help`, `oauth-draft-message-id --help`,
`oauth-draft-setup --help`.

## Setup — one-time

You need a Google OAuth client with the `https://mail.google.com/`
scope, and a refresh token issued against the Gmail account you use
for `security@<project>.apache.org` triage.

1. **Create a Google Cloud project** (if you don't already have one
   for this purpose). Enable the Gmail API.

2. **Create an OAuth client** of type *Desktop app*. Download the
   credentials JSON (call it `client_secrets.json`).

3. **Run the consent flow** with the downloaded `client_secrets.json`.
   `oauth-draft-setup` opens a browser tab against Google's consent
   screen, captures the auth code on a local-bound port, exchanges it
   for a refresh token, and writes the credentials file in the shape
   the other two scripts expect:

   ```bash
   uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-setup \
     /path/to/client_secrets.json
   ```

   Optional flags:

   | Flag | Purpose |
   |---|---|
   | `--from-address` | Address baked into the credentials file as the outgoing `From:`. Defaults to `$GMAIL_FROM`, then `git config user.email`. |
   | `--out` | Output path. Default: `~/.config/apache-magpie/gmail-oauth.json`. |
   | `--rm-client-secrets` | Delete the input `client_secrets.json` after writing the credentials file. |

   The script writes the credentials atomically with mode 600 and
   chmods the parent directory to 700. The refresh token it stores is
   the long-lived secret of the whole `oauth_curl` backend; treat
   the file like an SSH private key.

4. **Smoke-test** by running a dry-run thread search:

   ```bash
   uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-mark-read \
     --query 'in:inbox is:unread' --max 3
   ```

   This exercises `Credentials.load → refresh_access_token →
   threads.list` without modifying anything. A non-empty list of
   thread IDs (or *"Found 0 matching thread(s)"*) means the
   credentials work.

## How threading is guaranteed

When `oauth-draft-create` is invoked with `--thread-id`, the script
does three things, in order:

1. Refreshes a short-lived access token from the stored refresh token.
2. Reads the chronologically-last message in the thread and extracts
   its `Message-ID` header (and the existing `References` chain).
3. Builds an RFC822 MIME message with `In-Reply-To: <that-Message-ID>`
   and `References: <existing chain> <that-Message-ID>`, plus sets
   `threadId` in the Gmail API call.

Gmail's server-side threader attaches by `threadId`; every other mail
client that receives the message threads by `References` /
`In-Reply-To` chain. Both paths agree, so the draft lands on the same
conversation for everyone.

Pass `--no-reply-headers` to skip step 2 (useful only for smoke
testing — production drafts always want the headers set).

## Confidentiality

The refresh token grants full read/draft access to your Gmail. Treat
it like an SSH key:

- The setup script writes the file with mode 600 and chmods its parent
  directory to 700; do not loosen those.
- Do **not** commit the credentials file. The path lives outside the
  repo tree by default (`~/.config/apache-magpie/gmail-oauth.json`).
- Revoke the refresh token at
  <https://myaccount.google.com/permissions> if you suspect it has
  leaked.

## Test

```bash
cd tools/gmail/oauth-draft
uv run --group dev pytest
```

## Lint / type-check

```bash
cd tools/gmail/oauth-draft
uv run --group dev ruff check src tests
uv run --group dev ruff format --check src tests
uv run --group dev mypy
```

The `prek` hooks configured in `.pre-commit-config.yaml` at the
repository root run `ruff check`, `ruff format --check`, `mypy`,
and `pytest` on the project files automatically on every commit
that touches them.

## Referenced by

- [`../operations.md`](../operations.md#drafting-backends) — two-backend overview.
- [`../threading.md`](../threading.md) — threading guarantees per backend.
- [`../draft-backends.md`](../draft-backends.md) — the config knob.
