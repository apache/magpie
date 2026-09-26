<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Draft PR procedure

Companion to [`SKILL.md`](SKILL.md). The three actions Step 9 performs once `--draft-pr` is passed and the user explicitly confirms after the hand-back artefact.

The skill:

1. Shows the user the proposed PR title, body, and diff (one final review surface).
2. On explicit confirmation, opens a **draft** PR from the user's fork against `<upstream>:<default-branch>` with `gh pr create --web --draft`, pre-filling `--title` and `--body` (including the generative-AI disclosure block) so the human reviews them in the browser before submitting — per [`AGENTS.md` → *"Always open PRs with `gh pr create --web`"*](../../../../AGENTS.md#commit-and-pr-conventions).
   Never non-draft; never on autopilot; never submitted without the browser step.
3. Does NOT post to `<issue-tracker>`, self-assign, or transition workflow state — those remain the maintainer's actions.

Without `--draft-pr`, Step 9 is skipped entirely; the hand-back artefact is the terminal output.
