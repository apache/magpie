<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Draft PR procedure (optional)

Companion to [`SKILL.md`](SKILL.md). The full Step 8 flow: when it runs, what the skill does, and what it never does.

This step runs only if `--draft-pr` was passed AND the user
explicitly confirms after the hand-back artefact.

The skill:

1. Shows the user the proposed PR title, body, and diff.
2. On explicit confirmation, pushes the branch to the user's fork
   with `git-push-branch <worktree> <branch> fork <branch> new`
   (`--caller audit-finding-fix`, per
   [vetted-git-publish.md](vetted-git-publish.md), after the pre-push
   checks pass in the sandbox), then opens a **draft** PR from the
   fork against `<upstream>:<default-branch>` with
   `gh pr create --web --draft` (`git-pr-create` opens no drafts), pre-filling `--title` and
   `--body` so the human reviews everything in the browser before
   submitting.
3. Does NOT post to any tracker, self-assign, or transition state.

Without `--draft-pr`, this step is skipped entirely.

---
