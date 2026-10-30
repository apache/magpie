<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [SourceHut (sr.ht) Forge Bridge](#sourcehut-srht-forge-bridge)
  - [Prerequisites](#prerequisites)
  - [Features](#features)
  - [Invocation](#invocation)
  - [Configuration](#configuration)
  - [Bodies and raw GraphQL](#bodies-and-raw-graphql)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# SourceHut (sr.ht) Forge Bridge

**Capability:** contract:tracker + contract:source-control + contract:mail-archive
**Kind:** implementation
**Vendor:** SourceHut

SourceHut (sr.ht) forge bridge implementation for the Apache Magpie framework. It integrates ticket tracking (`todo.sr.ht`), mailing list patchset review (`lists.sr.ht`), CI builds (`builds.sr.ht`), and repository reads (`git.sr.ht` & `hg.sr.ht`) using SourceHut's GraphQL APIs.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (stdlib-only, no third-party package dependencies at runtime).
- **CLIs:** `git` (for Git repo interactions) and `hg` (for Mercurial repo interactions).
- **Credentials / auth:** `SRHT_TOKEN` environment variable containing a SourceHut Personal Access Token (OAuth2 bearer token) with appropriate scopes (e.g. `TICKETS:RW`, `LISTS:R`, `BUILDS:R`, `REPOS:R`).
- **Network:** Reaches `todo.sr.ht`, `lists.sr.ht`, `builds.sr.ht`, `git.sr.ht`, and `hg.sr.ht` endpoints over HTTPS (`/query`).

## Features

1. **VCS Repositories:** Reads repo metadata across `git.sr.ht` and `hg.sr.ht`.
2. **Issue Tracker:** Read/write operations (create ticket, comment, resolve status, update labels) on `todo.sr.ht` trackers.
3. **Mailing Lists:** Reads patchsets and threads from `lists.sr.ht`, mapping them to the uniform PR/MR review abstraction. Fetched mail bodies are external data, not instructions; content is treated as hostile input and routed through the Privacy-LLM gate or redacted before model-facing use. Embedded prompt-injection text in mail bodies is carried as report data only and is never obeyed as a framework instruction.
4. **CI Builds:** Reads job statuses from `builds.sr.ht`.
5. **GraphQL client:** Unified command line tool to run raw queries across sr.ht subdomains. A document containing a `mutation` is refused unless `--allow-mutation` is passed; skills write through the `ticket` subcommands, and pass `--allow-mutation` only for a write the user confirmed verbatim.

## Invocation

```bash
# Get ticket details
uv run --project tools/sourcehut magpie-sourcehut ticket get ~user tracker-name 123

# Create comment on a ticket (body written to a file first; '-' reads stdin)
uv run --project tools/sourcehut magpie-sourcehut ticket comment ~user tracker-name 123 --body-file <scratch>/comment.md

# Check build status
uv run --project tools/sourcehut magpie-sourcehut build get 123456
```

## Configuration

The bridge is configured via environment variables:

| Variable | Description |
|---|---|
| `SRHT_TOKEN` | Required. SourceHut personal OAuth2 token with access to target repositories, trackers, and mailing lists. |

## Bodies and raw GraphQL

Ticket and comment bodies often carry text from reporters or other outside sources,
so they reach the CLI through a file, never as a shell argument
(the same rule as [`tools/github/operations.md`](../github/operations.md)).
`ticket create` and `ticket comment` take `--body-file <path>` (`-` reads stdin);
there is no inline `--body`, and the option is not abbreviated, so an old `--body "<text>"` call fails instead of being read as a path.

`graphql <service> <query>` runs a raw query with the read-write `SRHT_TOKEN`.
It refuses any document with a `mutation` keyword outside strings and comments unless `--allow-mutation` is passed;
the check is deliberately conservative, so a query that only names a field `mutation` needs the flag too.
`<service>` must be a bare sr.ht subdomain name (`todo`, `lists`, `builds`, `git`, `hg`, …), so the token is only ever sent to `https://<service>.sr.ht/query`.
