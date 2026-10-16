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
  - [Subversion-hosted projects](#subversion-hosted-projects)
    - [What `probe` detects](#what-probe-detects)
    - [What setup writes](#what-setup-writes)
    - [Skills that assume GitHub](#skills-that-assume-github)
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
  1.9+, for `info --show-item` and `cleanup --remove-unversioned`; an
  older `svn` is reported as not installed and every operation errors).
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
source-control backend from `vcs_backend` in `<project-config>/project.md`
([*Tools enabled → Source control*](../../plugins/magpie-setup/templates/project.md#source-control)),
which they pass as `--backend` so a checkout of the wrong kind fails loudly.
`setup` writes `vcs_backend` and the Subversion URLs from
[`probe`](#subversion-hosted-projects); nobody has to know about `--backend` or `$MAGPIE_VCS`.
Backend-specific adopter knobs belong in the relevant
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
| Detect Subversion hosting | `probe` (JSON) | read, offline |
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

On a centralized backend (`svn`) the change becomes public at `commit`
and `new-branch` (a server-side copy), not at `push`, so whatever a skill
runs just before publishing (a confirmation naming the remote, a pre-push
scrub) must gate those operations instead.

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
| `new-branch <name>` | server-side `svn copy` of the current line of work to `branches/<name>`, then `svn switch` onto it; `<name>` is one path segment (not empty, `.` or `..`, no `/`) and is URL-quoted |
| `switch <ref>` | `trunk`, `branches/<n>`, `tags/<n>`, or a bare branch name (one segment, so `team/fix` is refused); a URL or `^/` path is used as-is |
| `stage <paths…>` | `svn add` for new paths (and unversioned parents), `svn delete` for versioned paths gone from disk, whether given directly or found under a given directory (as `git add <dir>` stages removals); versioned paths still on disk are a no-op |
| `commit -m` | `svn commit` of every modified or scheduled (`stage`d) path in the working copy — SVN has no staging area, so unrelated edits go too; unversioned files need `stage` first. Written straight to the server |
| `diff --cached` | error: no staging area |
| `diff --base <rev>` | the working copy against a **revision** (a number, `HEAD`, `BASE`, `COMMITTED`, `PREV` or `{DATE}`); a line-of-work name such as `main` or `trunk` is refused |
| `log` | server history up to `HEAD`, one `r<rev> <subject>` line per revision; `--grep` / `--author` are regexes, `--since` takes an ISO 8601 date. With `--grep` / `--author` / `--since`, `-n` caps the output only: the path's whole history (back to `--since`, if given) is fetched before filtering, which is slow on a large shared repository such as svn.apache.org |
| `cat <rev> <path>` | the working-copy path at `<rev>`, following copy history (so a revision from before a branch was created resolves through trunk). A path no longer in the working copy is read through the revision before the commit that deleted it on this line of work, which reads the line's log (slow on a large repository) |
| `fetch` | no-op: refs live on the server and every history read queries it |
| `push` | error: `commit` already published the change |

A caller using the Python API tells the models apart with
`VCSBackend.distributed`; a skill using the CLI checks for
`magpie-vcs detect` printing `svn`.

Supported scope, and what is not:

- **Layout.** Only the conventional `trunk` / `branches/<name>` /
  `tags/<name>` layout, read from the working copy's URL with the
  *rightmost* marker winning (`^/branches/projects/foo/trunk` is `foo`'s
  `trunk`). A checkout of a subdirectory that is itself named `trunk`,
  `branches` or `tags` is misread, and other repository organisations are
  not supported: there `branch` reports the repository-relative path and
  `new-branch` / name-based `switch` refuse (pass a URL or `^/` path to
  `switch`).
- **Branch names** are one path segment; nested names (`team/fix`) are
  refused by `new-branch` and by name-based `switch`. A branch or tag may
  be named `trunk` (`branches/trunk` is a branch, not the trunk).
- **Partial `new-branch`.** The server-side copy and the local switch are
  two steps. If the switch fails after the copy succeeded, the branch
  exists on the server and the working copy stays where it was; recover
  with `switch <name>`, not another `new-branch`.

### Adding a backend

A VCS bridge (e.g. #603 Jujutsu) implements a concrete `VCSBackend`
subclass — `detect()`, the read operations, the write operations — and
registers it in `BACKENDS`; nothing else changes: detection, dispatch,
the CLI, and every skill that calls `magpie-vcs` pick it up
automatically.

## Subversion-hosted projects

`magpie-vcs -C <checkout> probe` prints one JSON object saying whether the project is hosted in Subversion, and where.
[`setup config` and `setup adopt`](../../plugins/magpie-setup/skills/setup/config.md#step-3--scaffold-and-fill) run it and propose its `proposal` for `project.md`.
It is read-only and offline: it reads working-copy metadata and never runs a command that reaches a server.

```json
{
  "kind": "svn-working-copy",
  "svn_hosted": true,
  "svn": {"url": "https://svn.apache.org/repos/asf/foo/trunk", "repository_root": "https://svn.apache.org/repos/asf",
          "project_url": "https://svn.apache.org/repos/asf/foo", "line_of_work": "trunk",
          "layout": "trunk/branches/tags", "uuid": "…", "source": "svn info"},
  "proposal": {"vcs_backend": "svn", "svn_url": "https://svn.apache.org/repos/asf/foo",
               "svn_repository_root": "https://svn.apache.org/repos/asf", "upstream_default_branch": "trunk"},
  "notes": []
}
```

It also carries `path`, `backend` and `root`, as `detect` and `root` would print them.

### What `probe` detects

| `kind` | Evidence | Repository root |
|---|---|---|
| `svn-working-copy` | a `.svn/` directory at or above the path; read with `svn info --xml`, or from `.svn/wc.db` when `svn` 1.9+ is missing or fails | yes |
| `git-svn-clone` | `svn-remote.<name>.url` in the git config; the line of work is that URL plus the `fetch` path | from `.git/svn/.metadata` once git-svn has fetched, else `null` |
| `git-svn-mirror` | no `svn-remote`, but HEAD's message carries a `git-svn-id: <url>@<rev> <uuid>` trailer, as on a mirror built with git-svn | `null`: not knowable offline |
| `git`, `hg`, `fossil` | anything else that backend detects | — |
| `none` | no working copy | — |

`layout` is `trunk/branches/tags` when the URL contains one of those markers (the rightmost wins, as in the [`svn` backend](#subversion-centralized-model)), and `other` otherwise.
For `other`, `svn_url` is the checkout's own URL, `upstream_default_branch` is `null`, and a note says the backend's `new-branch` and name-based `switch` refuse there.

Not detected:

- **A mirror with no git-svn trailer**, such as one built by another converter, or a GitHub repository whose description or README says it mirrors Subversion.
  Both need the network or a guess; `probe` reports plain `git`, and the user says otherwise.
- **A project that moved from Subversion to Git.** Its old commits carry `git-svn-id`, but HEAD does not, so it is reported as `git`, which is right.
- **Local git-svn commits** are not a problem: the `svn-remote` config is read before HEAD.

A Git checkout inside an svn working copy is reported as `git`, with a note naming the working copy.

### What setup writes

On a Subversion-hosted project, setup proposes these `project.md` keys, and writes them only when the user confirms:

| Key | Value |
|---|---|
| `vcs_backend` | `svn` |
| `svn_url` | the project base URL, above `trunk` / `branches` / `tags` |
| `svn_repository_root` | the repository root, when `probe` knows it |
| `upstream_default_branch` | `trunk`, for the conventional layout only |

A `git-svn-clone` or `git-svn-mirror` checkout is Git: `magpie-vcs` drives it with the `git` backend, which cannot commit to Subversion.
With `vcs_backend: svn`, a skill passing `--backend svn` then fails on it until the user makes an `svn checkout` of the project; setup says so, and never runs the checkout itself.
A Git project's values are unchanged.

### Skills that assume GitHub

`upstream_repo` and `upstream_default_branch` are GitHub-shaped.
On a project with `vcs_backend: svn`:

- **Forge skills** read `upstream_repo` as a GitHub slug for pull requests, issues, Actions or the API: the `pr-management` family, `contributor-growth`, `reviewer-routing`, `pre-first-pr-check`, `ci-runner-audit` and `workflow-security-audit`.
  They apply only when the project really has a GitHub repository; with `upstream_repo` left `TODO`, they name the missing value when they need it instead of guessing one.
- **Dev-loop skills** run `git` inline in the upstream checkout: `security-issue-fix`, `issue-fix-workflow`, `issue-reproducer`, `issue-reassess`, `pairing-self-review`, `pairing-multi-agent-review`, `pr-management-code-review` and `pr-management-stack-review`.
  They work against an SVN working copy only once they call `magpie-vcs`; until then they need a Git checkout.
- **Skills that resolve `<default-branch>`** get `trunk`: the `issue` triage, stale-sweep, backlog and reassess-stats skills, `audit-finding-fix`, `flaky-test-triage`, the dependency and licence audits, `security-issue-invalidate`, `security-model-verify` and `release-prepare`.
  `trunk` is right wherever they only name the line of work; where they build a GitHub URL or a Git ref from it, they need the GitHub repository or Git checkout above.

## How to use

```bash
# run the tests
uv run --project tools/vcs --group dev pytest

# in a skill / shell, against an upstream checkout
uv run --project tools/vcs magpie-vcs -C ~/code/foo detect
uv run --project tools/vcs magpie-vcs -C ~/code/foo status
uv run --project tools/vcs magpie-vcs -C ~/code/foo probe
```

Exit codes: `0` success, `1` for `clean` when the tree is dirty, `2`
for any `VCSError` (unknown/unsupported backend, failed command).
