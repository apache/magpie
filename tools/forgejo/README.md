<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/forgejo/`](#toolsforgejo)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/forgejo/`

**Capability:** contract:tracker + contract:source-control + contract:change-request

**Kind:** implementation

**Vendor:** Forgejo / Gitea

Forgejo / Gitea REST substrate. Pure read/write wrapper used by every lifecycle phase (triage / intake / fix / resolve / stats). See [`tool.md`](tool.md) for the operation catalogue and the per-area files ([`issue-template.md`](issue-template.md), [`labels.md`](labels.md), [`operations.md`](operations.md), [`project-board.md`](project-board.md), [`status-rollup.md`](status-rollup.md)) for specifics.

This tool implements three capability contracts: `contract:tracker` (issues / boards / labels), `contract:source-control` (Git branch / commit / diff / push, documented in [`source-control.md`](source-control.md)), and `contract:change-request` — the pull-request review/merge gate driven by `tea pr`. On Forgejo/Gitea the `change-request` `land` verb resolves to `tea pr merge` (the forge lands and closes atomically).

## Prerequisites

- **Runtime:** Bash — this is a doc-only adapter; skills invoke the `tea` CLI (`tea`) and `git`, no local package.
- **CLIs:** `tea` (authenticated), `git` (source-control capability), `jq`.
- **Credentials / auth:** `tea login list` must show a logged-in user — every skill's Step 0 runs it. The `tea` config should be present or the `TEA_TOKEN` environment variable must be set.
- **Network:** The Forgejo/Gitea instance API (`/api/v1/`) and Git remote; source-control recipes are offline except explicit `fetch` / `push`.

## Configuration

Adopters select Forgejo-backed tracker, source-control, and change-request behavior through `<project-config>/project.md` repository keys such as `tracker_repo`, `upstream_repo`, and the source-control / change-request entries in the *Tools enabled* table. Forgejo issue body fields, labels, project-board configurations, and PR-management knobs live in the matching `<project-config>/*-config.md` files documented from `projects/_template/README.md`.
