<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Draft PR procedure (optional)

Companion to [`SKILL.md`](SKILL.md). The full Step 8 flow: when it runs, what the skill does, and what it never does.

This step runs only if `--draft-pr` was passed AND the user
explicitly confirms after the hand-back artefact.

The skill:

1. Shows the user the proposed PR title, body, and diff.
2. On explicit confirmation, opens a **draft** PR from the user's
   fork against `<upstream>:<default-branch>` with
   `gh pr create --web --draft`, pre-filling `--title` and
   `--body` so the human reviews everything in the browser before
   submitting.
3. Does NOT post to any tracker, self-assign, or transition state.

Without `--draft-pr`, this step is skipped entirely.

---
