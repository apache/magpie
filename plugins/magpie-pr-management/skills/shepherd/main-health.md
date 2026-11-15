<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# A red <default-branch>

1. Read the failing run: `gh run view <run-id> --repo <upstream> --log-failed`.
   Note which hook or test failed and on which files.
2. Find what broke it.
   Compare the failing run's commit with the last green one; the merges in between are the suspects.
   The usual culprit is a PR whose own CI could not see the problem, because PR runs check only the PR's diff:
   - a dependency bump (a linter or formatter) whose new release flags files the bump never touched;
   - a rename or move that left a reference elsewhere stale.
   A run that was cancelled rather than failed is not a red <default-branch>; check the next run.
3. Fix it on a fresh branch from <default-branch>.
   When a tool offers its own fix, apply it only where it cannot change behaviour, and say why in the commit (for example, a nested `if` that is the last branch of its `elif` chain).
   Commit the regenerated copies a hook produces along with the source.
4. Run [the pre-push gate](own-prs.md#the-pre-push-gate) over the whole tree, push to the viewer's fork, and draft the PR: what failed, which merge caused it, why that PR's CI missed it, and why the fix is safe.
   Show the draft; create the PR and enable auto-merge only once the maintainer confirms.
5. Tell the maintainer which open PRs will need a rebase once the fix lands.

When the culprit is a PR the maintainer approved, say so plainly; that is the information they need for the next bump.
