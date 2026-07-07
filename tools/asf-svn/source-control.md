<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [ASF SVN — source-control (VCS) capability](#asf-svn--source-control-vcs-capability)
  - [Centralized-model divergences](#centralized-model-divergences)
  - [What the skills require — SVN binding](#what-the-skills-require--svn-binding)
  - [ASF repository layout](#asf-repository-layout)
  - [`magpie-vcs` integration](#magpie-vcs-integration)
  - [When to replace this capability](#when-to-replace-this-capability)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# ASF SVN — source-control (VCS) capability

Shared reference for the **version-control operations** the skills run
against a Subversion working copy hosted on `svn.apache.org`. This is
the SVN binding of the abstract source-control capability defined in
[`tools/github/source-control.md`](../github/source-control.md) — read
that document for the full abstract operation set; this document covers
the SVN-specific binding and the centralized-model divergences.

## Centralized-model divergences

SVN is a **centralized** VCS. The abstract capability contract was
designed against a distributed model (Git). The following table
documents how each distributed assumption maps onto SVN's model:

| Distributed assumption | SVN reality |
|---|---|
| Local commits exist before push | No local commits — `svn commit` goes directly to the server; the working copy is always at a server revision |
| Cheap local branches via refs | Branches are directory copies: `svn copy trunk/ branches/<name>/` creates a branch on the server |
| Tags are lightweight refs | Tags are directory copies: `svn copy trunk/ tags/<name>/` — by convention immutable, but SVN does not enforce it |
| `fetch`/`push` split | `svn update` synchronises the working copy; `svn commit` writes to the server — there is no fetch-then-push sequence |
| Working copy is a full clone | A working copy is a partial checkout at a single URL; `svn checkout <url>` creates it; depth can be limited (`--depth empty`, `--depth files`) |
| `git worktree` for isolated checkouts | `svn checkout <url> <dir>` into separate directories — each is an independent working copy of the same repo |
| `git stash` for parking work | `svn diff > patch.diff` + `svn revert -R .` to park; `svn patch patch.diff` to restore — no built-in stash primitive |

A skill that targets the abstract source-control capability and is
operating over this binding must treat these as the actual primitives —
no Git shim is available.

## What the skills require — SVN binding

The dev-loop skills (`issue-fix-workflow`, `pr-management-code-review`,
`issue-reproducer`, `issue-reassess`) rely on the following abstract
operations. The SVN binding is shown alongside each:

| Abstract operation | SVN binding | Notes |
|---|---|---|
| Locate the repo root | `svn info --show-item repos-root-url` | Returns the repository root URL, e.g. `https://svn.apache.org/repos/asf` |
| Inspect working-copy state | `svn status` | `-q` to suppress unversioned items; `--xml` for machine-readable output |
| Current branch / line of work | `svn info --show-item url` → strip root to get path | e.g. `trunk`, `branches/foo`, `tags/1.2.3` |
| Create a line of work | `svn copy <from-url> <branch-url> -m "Branch for <purpose>"` | Server-side copy; the working copy is then switched with `svn switch <branch-url>` |
| Switch to a ref | `svn switch <url>` | Switches the working copy to the given URL (branch/tag) |
| Stage + record a change | `svn add <paths>` (new files), then `svn commit -m "<msg>"` | No two-phase stage/commit — `svn add` schedules; `svn commit` both stages and writes to the server |
| Show changes | `svn diff` | `--old <url>@<rev> --new <url>@<rev>` for cross-revision; `-r <rev>` for a single revision |
| History read | `svn log [-l <n>] [-r <rev>:<rev>]` | `--xml` for machine-readable; `--verbose` adds changed-path list |
| File at revision | `svn cat <url>@<rev>` | Reads a file at a specific revision without changing the working copy |
| Blame | `svn blame <path>` | `--xml` for machine-readable |
| Determine divergence base | `svn mergeinfo --show-revs eligible <trunk-url> <branch-url>` | `eligible SOURCE TARGET` lists revisions in SOURCE not yet in TARGET; with SOURCE=trunk, TARGET=branch this finds revisions on trunk not yet merged to the branch |
| Sync working copy | `svn update` | Brings the working copy to HEAD (or `-r <rev>` for a specific revision) |
| Park uncommitted work | `svn diff > patch.diff && svn revert -R .` | Save diff to file; restore with `svn patch patch.diff` |

Write-path operations (`svn commit`, `svn copy` for branch/tag
creation) stay gated on explicit user confirmation in the calling
skill, exactly as the Git write paths are.

## ASF repository layout

The canonical ASF SVN layout for a project at
`https://svn.apache.org/repos/asf/<project>/`:

```text
<project>/
  trunk/          # main line of development (equivalent to Git's main branch)
  branches/
    <name>/       # feature or maintenance branch
  tags/
    <name>/       # release tag (immutable by convention)
```

Checking out only what is needed avoids pulling the full history:

```bash
# shallow checkout of trunk (current files only, no history download)
svn checkout --depth files \
  https://svn.apache.org/repos/asf/<project>/trunk \
  <project>-trunk

# sparse checkout of a single subdirectory
svn checkout \
  https://svn.apache.org/repos/asf/<project>/trunk/path/to/subdir \
  subdir-wc
```

## `magpie-vcs` integration

The abstract `magpie-vcs` CLI ([`tools/vcs/`](../vcs/README.md))
detects SVN working copies and dispatches to the SVN backend. Until
the full SVN binding lands in `magpie-vcs` (tracked in
[apache/magpie#602](https://github.com/apache/magpie/issues/602)),
`magpie-vcs detect` correctly identifies SVN working copies and raises
an actionable error naming the tracking issue.

When the `#602` binding is complete, the `magpie-vcs` CLI becomes the
preferred interface — a skill can run `magpie-vcs diff` or
`magpie-vcs log` and the tool dispatches to the correct `svn` command
without the skill knowing which VCS is in use.

## When to replace this capability

This binding covers `svn.apache.org`-hosted projects. The same binding
applies to any SVN server (not only ASF's), but the repository URL
templates and `asf-authorization-template` roster paths are
ASF-specific. A non-ASF SVN project would use the same `svn` CLI
recipes with its own server URL.
