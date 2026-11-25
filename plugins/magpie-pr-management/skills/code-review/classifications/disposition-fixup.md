<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Action `FIXUP`

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `disposition` offers it, as the default, when the only thing between a `COMMENT` and an `APPROVE` is a set of `minor` / `nit` findings that each carry a `fixup`, and `--head-pushable` says the maintainer can push to the PR head.
Every approval gate still holds: green real CI, no unresolved thread, no standing `CHANGES_REQUESTED`, no unanswered question, a branch that merges cleanly.
A `major` or `blocking` finding is never fixed up — it goes back to the author.

Instead of asking the contributor for another round over small, mechanical points, the maintainer applies them and approves.

1. **Check out the PR head** on a local branch.
   Fetch it in the sandbox, from the main checkout, over HTTPS: `git fetch https://github.com/<upstream>.git +pull/<N>/head:refs/remotes/<upstream_remote>/pr-<N>` (`git-fetch` fetches upstream branches only, and a fork's head is not one).
   Then create the worktree with `uvx --from ~/.claude/magpie/vetted-ops vetted-op-git --caller pr-management-code-review git-worktree-add <checkout> <path> <local-branch> <head-sha>`, confirmed by the maintainer.
   When no `[git]` values are configured for this project, every `vetted-op-git` step refuses: hand the maintainer each git command instead, starting with `git worktree add -b <local-branch> <path> <head-sha>`.
2. **Apply exactly the `fixup.changes`**, nothing else. No drive-by edits, no behaviour beyond what each finding names.
3. **Run the checks** for what was touched: the affected tool's tests, then `uvx --from ~/.claude/magpie/vetted-ops vetted-op-checks <worktree> <workspace>/<paths-file>` in the sandbox, which runs the hooks on those paths and records what passed.
   `git-commit` refuses a staged path this record does not hold as it is staged, so never skip it.
   If a fixup turns out bigger than its one-line description, or a check fails, abandon it and fall back to `COMMENT` with the findings.
   To abandon it, discard the edits in the sandbox (`git -C <worktree> restore .`), then remove the worktree with `… git-worktree-remove <worktree>`, which refuses a worktree with changes.
4. **Show the diff and the commit message; confirm.** The message lists each change; add the project's attribution trailer per [`AGENTS.md`](../../../../../AGENTS.md#commit-and-pr-conventions).
   Stage and commit with the vetted operations, each confirmed by the maintainer: `… git-stage <worktree> <workspace>/<paths-file>` with the same paths file the checks ran on, then `… git-commit <worktree> <workspace>/<message-file>`, the trailer as the message file's last paragraph ([vetted-ops → Git operations the sandbox blocks](../../../../../tools/vetted-ops/README.md#git-operations-the-sandbox-blocks)).
   When no `[git]` values are configured for this project, hand the maintainer the `git commit` command instead.
   Once the fixup is pushed, remove the worktree with `… git-worktree-remove <worktree>`.
5. **Push to the PR head on confirmation**: the head repository and branch come from `gh pr view <N> --json headRepository,headRepositoryOwner,headRefName`. Pushing to a contributor's branch is visible to everyone watching the PR.
   A head branch on `<upstream>` that the policy's `upstream_push` allows goes through `… git-push-branch <worktree> <local-branch> upstream <head-branch> <head-sha>`; a head in a contributor's fork is outside what the vetted operations reach, so hand the maintainer the `git push --force-with-lease=<head-branch>:<head-sha> <head-repo-url> <local-branch>:<head-branch>` command to run.
6. **Wait for CI on the new head** before approving (Golden rule 8), then re-run `guard` with the pushed SHA.
   On the `FIXUP+APPROVE+AUTO-MERGE` path there is no wait for CI, but the review state is re-read: save `gql-cr-pr <N>` again, confirm its head is the fixup commit you pushed, and re-run `disposition` (with no findings left) so a failing or never-started run on the new head is caught and `render` pins the merge to the fixup SHA.
   Then approve the fixup head, re-save `gql-cr-pr`, release the workflow runs the push left held there (`release-runs --head <fixup sha>` — [`disposition-auto-merge.md`](disposition-auto-merge.md) step 3), and enable auto-merge straight away; GitHub holds the merge until the new head's required checks pass.
7. **Post an `APPROVE`** whose body says what the fixup changed: one bullet per change, with its file and the fixup commit SHA, so the contributor sees exactly what was done to their branch and why.
   No inline comments — the fixup resolved them.

Merging stays a separate, explicitly confirmed action — except that where the repository allows auto-merge, the default is `FIXUP+APPROVE+AUTO-MERGE`: after step 7, enable auto-merge as [`disposition-auto-merge.md`](disposition-auto-merge.md) describes, and GitHub merges once its own required checks pass.
Never push without the maintainer's yes in step 5, and never approve on the strength of a fixup whose CI has not finished.
