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
uvx --from ~/.claude/magpie/vetted-ops vetted-op-git --caller setup-upstream-fix <operation> <param> …
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
| Rebase onto the refreshed base | `git-rebase <worktree> <onto-sha> <expected-sha>`: `<onto-sha>` is the full SHA of `<upstream_remote>/<base>` (it must be on the policy's `pr_base`, which the operation fetches again itself), `<expected-sha>` the branch's current full SHA; a branch with merge commits is refused; it re-signs per your global git configuration, and on a conflict it aborts and names the paths |
| Finish a rebase that conflicted | start a new branch on `<onto-sha>`, then `git-cherry-pick <worktree> <commit-sha> <expected-sha>` for each of your commits in order, `<expected-sha>` the new branch's current tip; the one that conflicts aborts and is named: make that change again in the sandbox and commit it (Stage, Check, Commit below), then carry on with the next |
| Stage | `git-stage <worktree> <workspace>/<paths-file>`: the intended relative paths, one per line, never everything |
| Check | `uvx --from ~/.cache/apache-magpie/vetted-ops/current vetted-op-checks <worktree> <workspace>/<paths-file>`, inside the sandbox (it is never excluded from it, and it starts from this readable copy because the sandbox cannot read `~/.claude/magpie/`; in a framework checkout or a pinned snapshot, `uv run --project <framework>/tools/vetted-ops vetted-op-checks …`): runs the hooks on those paths and records the content they passed; fix what it reports and run it again |
| Commit | `git-commit <worktree> <workspace>/<message-file>`: refused unless the check passed every staged path with the content it is staged with; the operation takes no `--trailer`, so the attribution trailer is the message file's last paragraph |
| Push | `git-push-branch <worktree> <branch> fork <branch> <expected>`, after `prek run --hook-stage pre-push --from-ref <upstream_remote>/<base> --to-ref <branch>` passes in the sandbox; `<expected>` is `new` for a first push, else the remote branch's current full SHA, so a branch someone else moved is never overwritten |
| Open the pull request | `git-pr-create <worktree> <branch> "<title>" <workspace>/<body-file>`: from the policy's fork against its `pr_base`, as a ready (not draft) pull request; show the user the exact title and body first |
| Label it | `uvx --from ~/.claude/magpie/vetted-ops vetted-op --caller setup-upstream-fix pr-add-label <N> <label>`, once per label, from the sandbox: `<N>` is the number `git-pr-create` printed, and `<label>` one the policy's `[values] upstream_labels` lists by name; pick them from the repository's own taxonomy and show them with the title and body |
| Clean up after merge | `git-worktree-remove <worktree>` (no local changes only), then `git-delete-fork-branch <checkout> <branch> <head-sha>` for the branch on your fork: refused unless the forge reports the pull request merged with that branch at `<head-sha>` as its head |

**Fallback.** When no `[git]` values are configured for this project (the
operation refuses with *"no [git] values for <repository>"*; point the user
at the `["<repository>"]` table their `operator-git.toml` lacks), or there is
no approved policy, hand the user the equivalent `git` and
`gh pr create --web` commands to run themselves, as before. When it
refuses the caller (`not permitted to run`), name the `git-*` grant
`setup-upstream-fix` needs in the policy's `[callers]` table and hand over the
same commands; never retry with another skill's `--caller`. What the
operations do not cover keeps its current route: a draft pull request or a
base other than `pr_base` opens with `gh pr create --web`, which the user
submits from the browser, and a push to a repository other than the
policy's upstream and fork is a command the user runs.

<!-- END MAGPIE BLOCK: vetted-git-publish -->
