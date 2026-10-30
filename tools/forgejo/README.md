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

**Coverage:** partial

**Kind:** implementation

**Vendor:** Forgejo / Gitea

Forgejo / Gitea REST substrate. Pure read/write wrapper used by every lifecycle phase (triage / intake / fix / resolve / stats). See [`tool.md`](tool.md) for the operation catalogue and the per-area files ([`issue-template.md`](issue-template.md), [`labels.md`](labels.md), [`operations.md`](operations.md), [`project-board.md`](project-board.md), [`status-rollup.md`](status-rollup.md)) for specifics.

This tool implements three capability contracts: `contract:tracker` (issues / labels), `contract:source-control` (Git branch / commit / diff / push, documented in [`source-control.md`](source-control.md)), and `contract:change-request` — partial pull-request recipes driven by `tea pr` and REST endpoints. On Forgejo/Gitea the `change-request` `land` verb resolves to `tea pr merge` (the forge lands and closes atomically).

## Prerequisites

- **Runtime:** Bash — this is a doc-only adapter; skills invoke the `tea` CLI (`tea`) and `git`, no local package.
- **CLIs:** `tea` (authenticated), `git` (source-control capability), `curl`, `jq`.
- **Credentials / auth:** Every REST recipe in [`operations.md`](operations.md) (collaborator lookup, issue create, issue body edit, comments, PR create) sends `Authorization: token $TEA_TOKEN` to `$FORGEJO_HOST`, so both variables are required whenever those recipes run. The token value is stored in a private configuration file in the user's home directory (e.g. `~/.config/tea/token` or `~/.config/apache-magpie/user.md` per [`AGENTS.md` § Local setup](../../AGENTS.md#local-setup)) and exported to the agent's environment. `$FORGEJO_HOST` is the base URL including the scheme (`https://forge.example.org`), since the recipes build `$FORGEJO_HOST/api/v1/...` from it. For `tea` CLI operations, `tea login list` must show an authenticated login.
- **Network:** The Forgejo/Gitea instance host (`$FORGEJO_HOST`) must be added to the sandbox network allowlist, permitting access to the instance API (`/api/v1/`) and Git remote; source-control recipes are offline except explicit `fetch` / `push`.
- **Secure-setup conflict:** the REST recipes call `curl`, which the [shipped secure setup](../../docs/setup/secure-agent-setup.md#the-frameworks-own-claudesettingsjson) denies (`Bash(curl *)`).
  Under that setup only the `tea` recipes run from the agent; the REST-only operations are run by the user — see [`operations.md` § Running the REST recipes under the secure setup](operations.md#running-the-rest-recipes-under-the-secure-setup).

## Configuration

Adopters select Forgejo-backed tracker, source-control, and change-request behavior through `<project-config>/project.md` repository keys such as `tracker_repo`, `upstream_repo`, and the source-control / change-request entries in the *Tools enabled* table. Forgejo issue body fields, labels, and PR-management knobs live in the matching `<project-config>/*-config.md` files documented from `projects/_template/README.md`.
