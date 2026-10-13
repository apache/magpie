<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`magpie-vcs`](#magpie-vcs)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
  - [Why](#why)
  - [The abstraction](#the-abstraction)
  - [Backends](#backends)
    - [Subversion (centralized model)](#subversion-centralized-model)
    - [Adding a backend](#adding-a-backend)
  - [How to use](#how-to-use)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `magpie-vcs`

**Capability:** contract:source-control

**Kind:** implementation

**Vendor:** Git

Runnable implementation of the **source-control (VCS) capability**
documented in
[`tools/github/source-control.md`](../github/source-control.md). It
extracts the abstraction the dev-loop skills assume — branch, stage,
commit, diff, log, fetch, push, working-tree reset — out of inline
`git` calls into one backend-dispatching CLI.

A skill (or a person) runs the **abstract** operation:

```bash
uv run --project tools/vcs magpie-vcs -C <upstream> diff --base main
uv run --project tools/vcs magpie-vcs -C <upstream> log --grep ISSUE-123
```

The active backend is **detected** from the working copy (or forced
with `--backend` / `$MAGPIE_VCS`), so the same command works whatever
VCS the project enables under *Tools enabled → Source control*.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; stdlib-only (no runtime
  dependencies). The `dev` group pulls `pytest`, `ruff`, `mypy`.
- **CLIs:** Depends on the active backend — the tool shells out to the
  underlying VCS binary: `git`, `hg`, `fossil` or `svn` (Subversion
  1.9+, for `cleanup --remove-unversioned`).
- **Credentials / auth:** None of its own; operations that reach the
  remote inherit whatever auth the underlying VCS/remote needs. `svn`
  runs `--non-interactive`, so it uses a cached credential
  (`~/.subversion/auth/`) and fails rather than prompting.
- **Network:** For the distributed backends, local for read and
  local-write operations; `fetch` / `push` reach the project's remote
  (e.g. GitHub) over the network. For `svn` (centralized), `log`, `cat`,
  `diff --base`, `new-branch`, `switch` and `commit` reach the server.

## Configuration

The active backend is detected from the working copy or forced with
`--backend` / `$MAGPIE_VCS`. Skills get the checkout path from
`<project-config>/user.md` (or the resolved user config) and the expected
source-control backend from `<project-config>/project.md` *Tools enabled*
entries. Backend-specific adopter knobs belong in the relevant
`*-config.md` file rather than in this tool.

## Why

Before this tool the skills hard-coded `git …` inline. PR #609 added
the capability *contract* (`source-control.md`) and pointed each
git-using skill at it; this tool is the *implementation* of that
contract — the single place a non-Git VCS bridge plugs in, instead of
editing every skill.

## The abstraction

`VCSBackend` is the abstract interface; each operation maps to the
*What the skills require* table in `source-control.md`:

| Operation | CLI | Read/Write |
|---|---|---|
| Detect backend | `detect`, `backends`, `root` | read |
| Working-tree status | `status`, `clean` | read |
| Current branch | `branch` | read |
| Show changes | `diff [--base REF] [--cached] [paths…]` | read |
| History read | `log [-n N] [--grep P] [--author A] [--since S] [paths…]` | read |
| Create line of work | `new-branch <name>` | write |
| Switch ref | `switch <ref>` | write |
| Stage | `stage <paths…>` | write |
| Commit | `commit -m <msg>` | write |
| Sync from forge | `fetch [remote] [ref]` | write |
| Publish | `push [-u] <remote> <ref>` | write |
| Reset working copy | `reset-worktree` | write |

Write operations stay gated on explicit user confirmation **in the
calling skill**, exactly as the tracker write paths are — the tool does
not add its own prompt.

## Backends

| Backend | Status | Notes |
|---|---|---|
| `git` | **complete** | GitHub's native VCS; the default binding |
| `hg` (Mercurial) | **complete** | Mercurial VCS support |
| `fossil` | **complete** | Fossil SCM; pairs with the [`tools/fossil`](../fossil/) forge bridge |
| `svn` (Subversion) | **complete** | centralized model (`distributed = False`); see below |

### Subversion (centralized model)

The `svn` backend maps the operations onto SVN's centralized model, as
documented in [`tools/asf-svn/source-control.md`](../asf-svn/source-control.md#centralized-model-divergences):

| Operation | SVN behaviour |
|---|---|
| `branch` | the line of work under the `trunk` / `branches/<name>` / `tags/<name>` layout (e.g. `trunk`); outside that layout, the repository-relative path |
| `new-branch <name>` | server-side `svn copy` of the current line of work to `branches/<name>`, then `svn switch` onto it |
| `switch <ref>` | `trunk`, `branches/<n>`, `tags/<n>`, or a bare branch name; a URL or `^/` path is used as-is |
| `stage <paths…>` | `svn add` for new paths (and unversioned parents), `svn delete` for paths gone from disk; versioned paths are a no-op |
| `commit -m` | `svn commit` of **every** change in the working copy — SVN has no staging area — written straight to the server |
| `diff --cached` | error: no staging area |
| `log` | server history up to `HEAD`, one `r<rev> <subject>` line per revision; `--grep` / `--author` are regexes, `--since` takes an ISO 8601 date |
| `cat <rev> <path>` | the path as it was at `<rev>` (pegged URL), even if since moved or deleted |
| `fetch` | no-op: refs live on the server and every history read queries it |
| `push` | error: `commit` already published the change |

A caller that needs to tell the models apart checks
`VCSBackend.distributed`.

### Adding a backend

A VCS bridge (e.g. #603 Jujutsu) implements a concrete `VCSBackend`
subclass — `detect()`, the read operations, the write operations — and
registers it in `BACKENDS`; nothing else changes: detection, dispatch,
the CLI, and every skill that calls `magpie-vcs` pick it up
automatically.

## How to use

```bash
# run the tests
uv run --project tools/vcs --group dev pytest

# in a skill / shell, against an upstream checkout
uv run --project tools/vcs magpie-vcs -C ~/code/foo detect
uv run --project tools/vcs magpie-vcs -C ~/code/foo status
```

Exit codes: `0` success, `1` for `clean` when the tree is dirty, `2`
for any `VCSError` (unknown/unsupported backend, failed command).
