<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/github/`](#toolsgithub)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/github/`

**Capability:** contract:tracker + contract:source-control + contract:change-request

**Kind:** implementation

**MCP:** GitHub MCP (mcp__github__*)

**Vendor:** GitHub

GitHub REST + GraphQL substrate. Pure read/write wrapper used by every lifecycle phase (triage / intake / fix / resolve / stats). See [`tool.md`](tool.md) for the operation catalogue and the per-area files ([`issue-template.md`](issue-template.md), [`labels.md`](labels.md), [`operations.md`](operations.md), [`project-board.md`](project-board.md), [`status-rollup.md`](status-rollup.md)) for specifics.

This tool implements three capability contracts: `contract:tracker` (issues / boards / labels), `contract:source-control` (Git branch / commit / diff / push, documented in [`source-control.md`](source-control.md)), and `contract:change-request` — the pull-request review/merge gate driven by `gh pr`. GitHub is **no longer the sole change-request backend**: [`tools/change-request/`](../change-request/) defines the backend-neutral contract, and [`tools/jira-patch/`](../jira-patch/) and [`tools/mail-patch/`](../mail-patch/) implement it for JIRA+SVN and `[PATCH]`-mail projects. On GitHub the `change-request` `land` verb resolves to `gh pr merge` (the forge lands and closes atomically); the SVN-first backends delegate `land` to `contract:source-control`.

## Prerequisites

- **Runtime:** Bash — this is a doc-only adapter; skills invoke the `gh` CLI (`gh` / `gh api`) and `git`, no local package.
- **CLIs:** `gh` (authenticated), `git` (source-control capability), `jq` (used via `gh api --jq`).
- **Credentials / auth:** `gh auth status` must show a logged-in user with the needed scopes — every skill's Step 0 runs it.
- **Network:** `api.github.com` (REST + GraphQL) and `github.com` (the `git` remote); source-control recipes are offline except explicit `fetch` / `push`.

## Configuration

Adopters select GitHub-backed tracker, source-control, and
change-request behavior through `<project-config>/project.md` repository
keys such as `tracker_repo`, `upstream_repo`, and the source-control /
change-request entries in the *Tools enabled* table. GitHub issue body
fields, labels, project-board IDs, and PR-management knobs live in the
matching `<project-config>/*-config.md` files documented from
`projects/_template/README.md`.
