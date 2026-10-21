<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Action `FIXUP`

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `disposition` offers it, as the default, when the only thing between a `COMMENT` and an `APPROVE` is a set of `minor` / `nit` findings that each carry a `fixup`, and `--head-pushable` says the maintainer can push to the PR head.
Every approval gate still holds: green real CI, no unresolved thread, no standing `CHANGES_REQUESTED`, no unanswered question, a branch that merges cleanly.
A `major` or `blocking` finding is never fixed up — it goes back to the author.

Instead of asking the contributor for another round over small, mechanical points, the maintainer applies them and approves.

1. **Check out the PR head** on a local branch.
2. **Apply exactly the `fixup.changes`**, nothing else. No drive-by edits, no behaviour beyond what each finding names.
3. **Run the checks** for what was touched: the affected tool's tests and `prek run --files <touched files>`.
   If a fixup turns out bigger than its one-line description, or a check fails, abandon it and fall back to `COMMENT` with the findings.
4. **Show the diff and the commit message; confirm.** The message lists each change; add the project's attribution trailer per [`AGENTS.md`](../../../../../AGENTS.md#commit-and-pr-conventions).
5. **Push to the PR head on confirmation**: the head repository and branch come from `gh pr view <N> --json headRepository,headRepositoryOwner,headRefName`. Pushing to a contributor's branch is visible to everyone watching the PR.
6. **Wait for CI on the new head** before approving (Golden rule 8), then re-run `guard` with the pushed SHA.
7. **Post an `APPROVE`** whose body says what the fixup changed: one bullet per change, with its file and the fixup commit SHA, so the contributor sees exactly what was done to their branch and why.
   No inline comments — the fixup resolved them.

Merging stays a separate, explicitly confirmed action.
Never push without the maintainer's yes in step 5, and never approve on the strength of a fixup whose CI has not finished.
