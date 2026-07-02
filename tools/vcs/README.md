<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`magpie-vcs`](#magpie-vcs)
  - [Prerequisites](#prerequisites)
  - [Why](#why)
  - [The abstraction](#the-abstraction)
  - [Backends](#backends)
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
  underlying VCS binary. `git` for the complete backend; `hg` / `svn` are
  detected but their bindings are not yet implemented.
- **Credentials / auth:** None of its own; write operations (`fetch`,
  `push`) inherit whatever auth the underlying VCS/remote needs.
- **Network:** Local for read and local-write operations; `fetch` / `push`
  reach the project's remote (e.g. GitHub) over the network.

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
| `svn` (Subversion) | extension point | detected; centralized model (`distributed = False`) → [#602](https://github.com/apache/magpie/issues/602) |

Detection is real for every backend (so `magpie-vcs detect` reports the
working copy's VCS correctly); the non-Git/non-Hg backends raise an actionable
`VCSError` naming their tracking issue until the full binding lands.

### Adding a backend

A VCS bridge (e.g. #602 Subversion) implements the full binding by
replacing that backend's `_UnimplementedBackend` base with a concrete
`VCSBackend` subclass — `detect()`, the read operations, the write

operations — and nothing else changes: detection, dispatch, the CLI,
and every skill that calls `magpie-vcs` pick it up automatically.

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
