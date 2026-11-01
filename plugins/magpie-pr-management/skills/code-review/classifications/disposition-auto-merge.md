<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Action `APPROVE+AUTO-MERGE` / `FIXUP+APPROVE+AUTO-MERGE`

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `disposition` makes it the default when the repository allows auto-merge (`autoMergeAllowed`), the viewer can enable it on this PR (`viewerCanEnableAutoMerge`), and the action ends in an `APPROVE` — a plain `APPROVE`, or a [`FIXUP`](disposition-fixup.md) that earns one.
It is never offered on a self-authored PR, on a PR that already has auto-merge enabled, on a branch that conflicts, or while an approval gate is open — except running CI, which auto-merge holds instead of gating.
Plain `APPROVE` and `FIXUP` stay in the overrides unless CI is still running; a repository without auto-merge sees no change.

1. **Post the `APPROVE`** as usual — immediately, even while real CI is still running (`ci_pending_held_by_auto_merge`); for the fixup variant, right after the push ([`disposition-fixup.md`](disposition-fixup.md) step 6).
   Failing CI, a rollup green from bot checks only, and workflows waiting for approval still rule it out (Golden rule 8); `ci_action` names the run to approve or re-run first.
2. **Re-run `guard`** against the head the approval was made on. New commits since → stop; do not enable auto-merge on a head nobody reviewed.
3. **Run `auto_merge_command`** from `render --auto-merge`: `gh pr merge <N> --repo <repo> --auto --<method>`, with the method from the viewer's default merge method for the repository (`viewerDefaultMergeMethod`, squash when unknown).
   It is a separate write; the maintainer's confirmation of this disposition covers it, and the confirmation prompt names it.
4. **Report** that auto-merge is on. GitHub holds the merge itself until the required checks pass and every conversation the branch rules require is resolved, so "enabled" is not "merged".

Disabling it again is `gh pr merge <N> --repo <repo> --disable-auto`, on the maintainer's word.
