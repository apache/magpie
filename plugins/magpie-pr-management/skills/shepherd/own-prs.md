<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Acting on your own PR

One section per Step 3 action.
Work on one PR at a time, in the main checkout, on a local branch made for it; switch back to <default-branch> and delete the local branch once the push is done.

## `rerun`

The run ID is in the failed check's URL (`…/actions/runs/<run-id>/job/…`).
Before proposing the rerun, confirm the job was cancelled at its time limit, not failed, from the step list rather than the log — a full job log runs to tens of thousands of tokens:

```bash
gh run view <run-id> --repo <upstream> --json jobs --jq '.jobs[] | select(.conclusion != "success") | {name, conclusion, startedAt, completedAt, steps: [.steps[] | {name, conclusion, startedAt, completedAt}]}'
```

A cancelled step with every earlier step successful, ending at the job's limit, is a timeout; the step timings show where the time went (a cache restore or an environment install taking minutes is the usual cause), so say so.
Read a log only for a failed step, and only that step's: `gh run view <run-id> --repo <upstream> --log-failed`.
A step that runs many hooks reports them all as one step, so a cancelled hook step still needs `--log-failed` to confirm every hook before the cancel passed.

```bash
gh run rerun <run-id> --repo <upstream> --failed
```

A second timeout on the same PR, or timeouts across several PRs on the same day, is worth reporting as a pattern: the limit may be too tight for the slow runners.

## `fix-failure` and `fix-comment`

1. Fetch the head and branch from it: `git fetch <head-repo-url> <head-branch>`, then `git switch --no-track -c <local-branch> FETCH_HEAD`.
2. Reproduce the failure locally with the same scope CI used.
   A monorepo that lints each workspace member separately can lint a copied or generated tree as its own member; run the failing hook the way CI does, not only on the package you edited.
3. Fix it. Code-scanning notes have known shapes:
   - *cyclic import* — an import deferred into a function only hides the cycle; move the shared code into a module both import at the top, and keep the old names importable where callers or tests use them (mark them as explicit re-exports so the linter does not drop them);
   - *unnecessary lambda* — check whether the lambda is there for late binding (a test patching the module-level name) before replacing it, and keep that patch working;
   - *empty except* — say in a comment why the exception is ignored, or stop ignoring it.
   After moving code, update every test that patches a path through the old module.
4. Run [the pre-push gate](#the-pre-push-gate), then stage the changed paths with `git-stage` and commit with `git-commit`, the message in a `<workspace>` file ending with the project's attribution trailer as its own last paragraph.
   Both are vetted operations ([vetted-git-publish.md](vetted-git-publish.md), `--caller pr-management-shepherd`), confirmed by the user; they run no hooks, so when the gate rewrites files (a generated copy, a formatter), stage what it changed before committing.
5. Propose the push to the PR's head branch: `git-push-branch <worktree> <local-branch> <target> <head-branch> <sha-you-last-pushed>`, where `<target>` is `fork` for a head in the policy's fork, or `upstream` for a head branch on `<upstream>` that the policy's `upstream_push` allows.
   A head anywhere else, or a project with no `[git]` values configured, gets the `git push` command for the user to run.

## `rebase`

Fetch <default-branch> into a full ref name that cannot clash with a local branch — `git-fetch <checkout> <default-branch>`, which writes `refs/remotes/<upstream_remote>/<default-branch>` (or, as a plain read, `git fetch <upstream-url> <default-branch>:refs/remotes/<name>/<default-branch>`) — and rebase onto that full ref name.
A short name that matches a local branch makes git warn *"refname is ambiguous"* and rebase onto the wrong commit.

Conflicts in generated content (token stamps, regenerated blocks, rendered tables) are resolved by regenerating it, never by picking a side by hand.
Any other conflict: stop and show it to the maintainer.

After the rebase, run [the pre-push gate](#the-pre-push-gate) and propose the push with its lease, `git-push-branch <worktree> <local-branch> <target> <head-branch> <sha-you-last-pushed>`, as in [`fix-failure`](#fix-failure-and-fix-comment) step 5.
With `[git]` values configured, the rebase itself is `git-rebase <worktree> <onto-sha> <expected-sha>`: it re-signs the replayed commits per the maintainer's global git configuration, which the sandbox cannot reach, and on a conflict it aborts and names the conflicting paths, to resolve in the sandbox as above.
Without them, a rebase in a linked worktree the session did not create runs in a scratch clone, and `git-worktree-sync` then moves the worktree to the rebased commit.

## `enable-auto-merge`

```bash
gh pr merge <N> --repo <upstream> --auto --squash
```

Use the repository's usual merge method when it is not squash.
`gh pr merge --auto` prints nothing on success; confirm with `gh pr view <N> --repo <upstream> --json autoMergeRequest` rather than running it again.

## The pre-push gate

A PR's CI checks the PR's own diff; the run on <default-branch> checks the whole tree.
A file the PR did not touch but broke (a moved anchor, a renamed import, a lint rule a dependency bump introduced) passes on the PR and fails on <default-branch> after the merge.
Before every push, run the project's whole-tree check minus its tests, then the tests for what the branch changed, as the project's contributing guide prescribes.
In this framework's own repository that is [`AGENTS.md` → Local setup](../../../../AGENTS.md#local-setup).
