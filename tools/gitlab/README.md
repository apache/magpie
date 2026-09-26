<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [GitLab bridge](#gitlab-bridge)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
  - [Operations](#operations)
  - [Usage](#usage)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# GitLab bridge

**Capability:** contract:tracker + contract:source-control + contract:change-request

**Coverage:** `partial`

**Kind:** implementation

**Vendor:** GitLab

GitLab forge, issue tracker, and merge request bridge for Apache Magpie.
Provides 100% offline-tested, deterministic API access to GitLab instances,
following strict vendor-neutrality rules.

This bridge implements a `partial` read-only foundation for repository
metadata context under `contract:source-control`, issue listing and fetching
under `contract:tracker`, and merge request discovery, diffs, commits, and
CI pipeline status under `contract:change-request`. Partial adapters may
implement named contract verbs, but they do not satisfy the complete contract
and must not be advertised as complete/selectable backends. Write operations
and issue/MR mutations remain out of scope for this foundation.

## Prerequisites

- **Runtime:** Python 3.11+ via `uv`.
- **CLIs:** `uv`.
- **Credentials / auth:** `GITLAB_TOKEN` (Personal Access Token, OAuth Bearer token)
  or `CI_JOB_TOKEN` with API access. Tokens are optional for unauthenticated reads
  on public projects.
- **Auth scheme override:** `GITLAB_AUTH_SCHEME` (`PrivateToken`, `Bearer`, `JobToken`)
  can be set to override header selection explicitly.
- **Network:** Access to the configured GitLab instance; `GITLAB_INSTANCE_URL`
  defaults to `https://gitlab.com`.

## Configuration

Set `GITLAB_TOKEN` in your environment (or `user.md`):

```bash
export GITLAB_TOKEN="glpat-..."
```

For self-hosted instances (e.g. Debian Salsa, GNOME):

```bash
export GITLAB_INSTANCE_URL="https://salsa.debian.org"
```

To explicitly force an authentication scheme (e.g. OAuth Bearer token vs Private Token):

```bash
export GITLAB_AUTH_SCHEME="Bearer"
```

## Operations

See [tool.md](tool.md) for the full operations catalogue and contract mapping.

## Usage

List open issues for a project:

```bash
uv run --project tools/gitlab magpie-gitlab issue list <project>
```

Get a merge request diff:

```bash
uv run --project tools/gitlab magpie-gitlab mr diff <project> <mr_iid>
```
