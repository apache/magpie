<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Publishing through `vetted-op-git`

Companion to [`SKILL.md`](SKILL.md). The git steps from a change to an open pull request, for every step that points here (generated shared block, byte-identical copy).

<!-- BEGIN MAGPIE BLOCK: vetted-git-publish — generated from tools/dev/blocks/vetted-git-publish.md -->

**Publishing through `vetted-op-git`.** The git steps between a change and an
open pull request run as vetted operations outside the sandbox, never as raw
`git` or `gh` commands. Each call is a write the user confirms, one call at a
time; nothing here runs unattended. Launch every call with the literal `~`
path, which is the only spelling agent-guard accepts:

```bash
uvx --from ~/.claude/magpie/vetted-ops vetted-op-git --caller audit-finding-fix <operation> <param> …
```

The policy is found from the working directory, so run the calls from the
directory whose vetted-ops policy names the target repository as `[repos]
upstream`. Where your clones, worktrees and fork are comes from your own
`~/.config/apache-magpie/vetted-ops/operator-git.toml` (one table per
upstream repository), laid over the policy's `[git]` table; `vetted-op-git
policy` prints the effective values. `<checkout>` is a main checkout its
`checkouts` lists, and `<worktree>` is that checkout or one of its linked
worktrees. The paths file,
commit message and pull-request body are files you write into `<workspace>`
first; the operation reads exactly that file.

| Step | Operation |
|---|---|
| Refresh the base | `git-fetch <checkout> <base>`, into `refs/remotes/<upstream_remote>/<base>` |
| Branch in a new worktree | `git-worktree-add <checkout> <path> <branch> <start-sha>`: `<path>` sits directly inside a `[git] worktree_roots` directory, `<start-sha>` is the full SHA of `<upstream_remote>/<base>` (`git rev-parse` in the sandbox) |
| Move an existing worktree | `git-worktree-sync <worktree> <commit-sha>` (clean worktree only) |
| Stage | `git-stage <worktree> <workspace>/<paths-file>`: the intended relative paths, one per line, never everything |
| Check | `uvx --from ~/.claude/magpie/vetted-ops vetted-op-checks <worktree> <workspace>/<paths-file>`, inside the sandbox (it is never excluded from it): runs the hooks on those paths and records the content they passed; fix what it reports and run it again |
| Commit | `git-commit <worktree> <workspace>/<message-file>`: refused unless the check passed every staged path with the content it is staged with; the operation takes no `--trailer`, so the attribution trailer is the message file's last paragraph |
| Push | `git-push-branch <worktree> <branch> fork <branch> <expected>`, after `prek run --hook-stage pre-push --from-ref <upstream_remote>/<base> --to-ref <branch>` passes in the sandbox; `<expected>` is `new` for a first push, else the remote branch's current full SHA, so a branch someone else moved is never overwritten |
| Open the pull request | `git-pr-create <worktree> <branch> "<title>" <workspace>/<body-file>`: from the policy's fork against its `pr_base`, as a ready (not draft) pull request; show the user the exact title and body first |
| Clean up after merge | `git-worktree-remove <worktree>` (no local changes only) |

**Fallback.** When no `[git]` values are configured for this project (the
operation refuses with *"no [git] values for <repository>"*; point the user
at the `["<repository>"]` table their `operator-git.toml` lacks), or there is
no approved policy, hand the user the equivalent `git` and
`gh pr create --web` commands to run themselves, as before. When it
refuses the caller (`not permitted to run`), name the `git-*` grant
`audit-finding-fix` needs in the policy's `[callers]` table and hand over the
same commands; never retry with another skill's `--caller`. What the
operations do not cover keeps its current route: a draft pull request or a
base other than `pr_base` opens with `gh pr create --web`, which the user
submits from the browser, and a push to a repository other than the
policy's upstream and fork is a command the user runs.

<!-- END MAGPIE BLOCK: vetted-git-publish -->
