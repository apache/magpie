<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [GitHub — source-control (VCS) capability](#github--source-control-vcs-capability)
  - [What the skills require](#what-the-skills-require)
  - [Distributed-VCS assumptions](#distributed-vcs-assumptions)
  - [When to replace this capability](#when-to-replace-this-capability)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# GitHub — source-control (VCS) capability

Shared reference for the **version-control operations** the skills run
against a local working copy of the project's source. On the GitHub
tool this capability is backed by **Git** (`git` + `git worktree`),
which is GitHub's native VCS.

This is a *distinct* capability from the tracker / project-board
surface documented in [`operations.md`](operations.md): those recipes
talk to the GitHub API over `gh`; the recipes here operate on a local
checkout with the `git` binary and never touch the network except for
explicit `fetch` / `push`. A project can in principle pair GitHub's
tracker with a different VCS, or a different forge with Git — see
[*When to replace this capability*](#when-to-replace-this-capability).

This contract has a runnable implementation in
[`tools/vcs/`](../vcs/README.md) (`magpie-vcs`): one abstract
`VCSBackend` interface, a complete Git backend, and detected extension
points for the non-Git bridges. A skill can call the abstract operation
(`magpie-vcs diff`, `magpie-vcs log`) instead of a raw `git` command and
let the tool dispatch to whichever backend governs the working copy. The
Git-binding tables below are the contract that tool implements.

## What the skills require

The dev-loop skills (`issue-fix-workflow`, `pr-management-code-review`,
`issue-reproducer`, `issue-reassess`) and the `setup-steward` worktree
machinery rely on the following abstract operations. The Git binding is
shown alongside each; a sibling VCS tool provides its own binding for
the same abstract operation.

| Abstract operation | Git binding | Used by |
|---|---|---|
| Locate the repo root / common dir | `git rev-parse --show-toplevel` / `--git-common-dir` / `--git-dir` | worktree setup, all dev-loop skills |
| Inspect working-copy state | `git status` (`-s` / `--short`) | fix-workflow, code-review pre-flight |
| Create / switch a line of work | `git checkout` / `git switch`, `git branch` | fix-workflow (branch per fix) |
| Stage + record a change | `git add`, `git commit -m` | fix-workflow |
| Show changes | `git diff` (`--cached`, `<base>`) | code-review, fix-workflow |
| History read | `git log` (`--oneline` / `--grep` / `--author` / `--since`), `git show` | reproducer, reassess, nomination |
| Determine divergence base | `git merge-base`, `git rev-parse` | code-review (diff against base) |
| Sync with the forge | `git fetch [origin]`, `git push [-u]` | fix-workflow hand-off |
| Re-apply onto an updated base | `git rebase` | triage rebase action |
| Isolated checkouts | `git worktree add` / `list --porcelain` | `setup-steward` worktree flow |
| Park uncommitted work | `git stash --include-untracked` | fix-workflow safety |

Write-path operations (`commit`, `push`, `rebase`) stay gated on
explicit user confirmation in the calling skill, exactly as the
tracker write paths are.

## Distributed-VCS assumptions

The Git binding assumes a **distributed** model: local commits,
cheap branches, a `worktree` primitive, and a `fetch`/`push` split
from the forge. Skills written against this capability should treat
those as the *abstract* contract, not as guaranteed primitives — a
centralized backend (e.g. Subversion, Perforce) maps "branch + local
commit + push" onto a different shape (changelists, server-side
branches) and its tool doc must spell out the divergence.

## When to replace this capability

Source control is a separable capability: any VCS that can provide the
abstract operations above can be plugged in by creating a sibling
`tools/<vcs>/` directory with its own `source-control.md` binding and
listing it in the project manifest under *Tools enabled* (the
*Source control* row). The generic skill logic — *"branch off the
default branch, commit the fix, push for review"* — does not change
when the VCS changes; only the bindings in the tool doc do.

Tracked VCS bridges that implement this capability against a non-Git
backend:

- Mercurial (Hg) — apache/magpie#601
- Apache Subversion (SVN) — apache/magpie#602
- Jujutsu (jj) — apache/magpie#603
- Fossil — apache/magpie#604
- Perforce / Helix Core — apache/magpie#605

Forge bridges that pair a non-GitHub forge with this capability live
alongside the tracker bridges (GitLab #305, Forgejo/Gitea #310,
Bitbucket #606, SourceHut #607 — the last also exercising the Hg
binding).
