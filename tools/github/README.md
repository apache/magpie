<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/github/`](#toolsgithub)
  - [Prerequisites](#prerequisites)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/github/`

**Capability:** contract:tracker

GitHub REST + GraphQL substrate. Pure read/write wrapper used by every lifecycle phase (triage / intake / fix / resolve / stats). See [`tool.md`](tool.md) for the operation catalogue and the per-area files ([`issue-template.md`](issue-template.md), [`labels.md`](labels.md), [`operations.md`](operations.md), [`project-board.md`](project-board.md), [`status-rollup.md`](status-rollup.md)) for specifics.

## Prerequisites

- **Runtime:** Bash — this is a doc-only adapter; skills invoke the `gh` CLI (`gh` / `gh api`) and `git`, no local package.
- **CLIs:** `gh` (authenticated), `git` (source-control capability), `jq` (used via `gh api --jq`).
- **Credentials / auth:** `gh auth status` must show a logged-in user with the needed scopes — every skill's Step 0 runs it.
- **Network:** `api.github.com` (REST + GraphQL) and `github.com` (the `git` remote); source-control recipes are offline except explicit `fetch` / `push`.
