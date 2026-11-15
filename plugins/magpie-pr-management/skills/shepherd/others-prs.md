<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Everyone else's PRs

[`pr-management-code-review`](../code-review/SKILL.md) reviews each one: findings, disposition, fixup, the drafted review and posting are its job, under its confirmation gates.
This file covers only what comes around it.

## A contributor replied *"fixed"* to every comment

Replies are claims; verify each against the new head before drafting anything.
For more than a few comments, delegate the check to a read-only subagent: give it the original comments, the replies, the new head as a fetched ref, and the reference implementation a comment pointed to; ask for VERIFIED / PARTIAL / NOT FIXED per comment with `file:line` evidence, plus any new problem the fixes introduced.
Then spot-check its strongest claims yourself — a subagent's report is model output, not evidence.
Check that a fix works against the real interface, not only against the PR's own mocks: a test that mocks the wrong shape passes while the code does nothing.

When the maintainer asks for a fixup on the contributor's branch, `maintainerCanModify` must be true.
Commit as in [`own-prs.md`](own-prs.md#fix-failure-and-fix-comment), push to the contributor's head repository, and draft a review that explains the commit, tells them to pull, and lists what is still open.
The same mistake in already-merged code is a separate fix PR, not part of the contributor's PR.

## A bot's lock-file bump

Check that each new version is past the project's cooldown and that CI passed.
Then run the whole-tree check for the bumped tool locally before approving: the bump's own CI checks only the lock file, so a linter or formatter release that flags untouched files fails only on <default-branch>, after the merge.
Route the approval through `pr-management-code-review` (an `APPROVE`, with auto-merge where the repository allows it).

## Already approved and `CLEAN`

Another maintainer approved it, CI is green, and no thread is open: print `gh pr merge <N> --repo <upstream> --squash` for the maintainer to run.
This skill does not merge.

## Waiting on its author

Changes requested and no push since: say so in the report and do nothing else.
