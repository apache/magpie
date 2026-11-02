<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Action `APPROVE+AUTO-MERGE` / `FIXUP+APPROVE+AUTO-MERGE`

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `disposition` makes it the default when the repository allows auto-merge (`autoMergeAllowed`), the viewer can enable it on this PR (`viewerCanEnableAutoMerge`), and the action ends in an `APPROVE` — a plain `APPROVE`, or a [`FIXUP`](disposition-fixup.md) that earns one.
It is never offered on a self-authored PR, on a PR that already has auto-merge enabled, on a branch that conflicts, or while an approval gate is open — except running CI, which auto-merge holds instead of gating.
Plain `APPROVE` and `FIXUP` stay in the overrides unless CI is still running; a repository without auto-merge sees no change.

1. **Post the `APPROVE`** as usual — immediately, even while real CI is still running (`ci_pending_held_by_auto_merge`), provided every running check is a required one (auto-merge waits only for those; a running check that is not required keeps the CI gate); for the fixup variant, right after the push ([`disposition-fixup.md`](disposition-fixup.md) step 6).
   Failing CI, a rollup green from bot checks only, and workflows waiting for approval still rule it out (Golden rule 8); `ci_action` names the run to approve or re-run first.
2. **Refresh the liveness read and re-run `guard`** against the head the approval was made on — save `gql-pr-liveness <N>` again first, so `guard` is not reading the pre-post copy. New commits since → stop; do not enable auto-merge on a head nobody reviewed.
3. **Release held workflow runs at the head.** Auto-merge only works if the required checks run, and a push — the fixup, or a contributor push the guard just saw — can leave the head's runs held in `action_required`.
   Read them per head (the repository-wide `runs-action-required` list is capped at 1000 and can miss them):

   ```bash
   uv run --project <framework>/tools/pr-management pr-management code-review release-runs --saved-dir <workspace>/saved --pr <N> --viewer <viewer> --head <full head sha> [--reviewed-head <sha>]
   ```

   Re-save `gql-cr-pr <N>` after the approval posted first: `release-runs` takes the viewer from that read (refusing a missing or different `--viewer`), refuses a head the read does not show, and releases only a head the viewer has an `APPROVED` review on — or, with `--reviewed-head`, a single commit whose only parent is the approved head and which carries a verified signature by the viewer with the viewer as its only linked author.
   Author names and emails are free text and prove nothing; releasing a run executes that head's code in CI, which is exactly what first-time-contributor approval guards.
   Save the `runs-at-head` read it names under `needs` and re-run it. For each `plan` step, run `workflow-approve <run_id>` through `vetted-op` (it approves first-time-contributor runs); pass its exit code and output to `pr-management code-review release-result --op workflow-approve --exit-code <rc> --output-file <file>`.
   `next_op: run-rerun` means GitHub answered *"This workflow run is not waiting for approval"* (HTTP 403): run `run-rerun <run_id>` and classify that the same way; `already-running` is done.
   A run that still fails to release is reported to the maintainer, and auto-merge then waits on checks that may never come.
4. **Run `auto_merge_command`** from `render --auto-merge`: `gh pr merge <N> --repo <repo> --auto --<method> --match-head-commit <reviewed head SHA>`, with the method from the viewer's default merge method for the repository (`viewerDefaultMergeMethod`, squash when unknown).
   `--match-head-commit` makes GitHub refuse if the head moved after the guard, so a later push can never ride the approval into a merge.
   `render --auto-merge` re-runs the `disposition` gates itself — pass it the same `--viewer` and flags (`--unanswered-question`, `--addressed-thread`, `--head-pushable`) — and refuses unless they still say auto-merge is eligible.
   It is a separate write; the maintainer's confirmation of this disposition covers it, and the confirmation prompt names it.
5. **Report** that auto-merge is on, and which held runs were released. GitHub holds the merge itself until the required checks pass and every conversation the branch rules require is resolved, so "enabled" is not "merged".

Disabling it again is `gh pr merge <N> --repo <repo> --disable-auto`, on the maintainer's word.
