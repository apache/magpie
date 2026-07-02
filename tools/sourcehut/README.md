<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [SourceHut (sr.ht) Forge Bridge](#sourcehut-srht-forge-bridge)
  - [Prerequisites](#prerequisites)
  - [Features](#features)
  - [Invocation](#invocation)
  - [Configuration](#configuration)

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
3. **Mailing Lists:** Reads patchsets and threads from `lists.sr.ht`, mapping them to the uniform PR/MR review abstraction.
4. **CI Builds:** Reads job statuses from `builds.sr.ht`.
5. **GraphQL client:** Unified command line tool to execute arbitrary queries/mutations across sr.ht subdomains.

## Invocation

```bash
# Get ticket details
uv run --project tools/sourcehut magpie-sourcehut ticket get ~user/tracker-name 123

# Create comment on a ticket
uv run --project tools/sourcehut magpie-sourcehut ticket comment ~user/tracker-name 123 --body "Nice fix!"

# Check build status
uv run --project tools/sourcehut magpie-sourcehut build get 123456
```

## Configuration

The bridge is configured via environment variables:

| Variable | Description |
|---|---|
| `SRHT_TOKEN` | Required. SourceHut personal OAuth2 token with access to target repositories, trackers, and mailing lists. |
