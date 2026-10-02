<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Draft PR procedure

Companion to [`SKILL.md`](SKILL.md). The three actions Step 9 performs once `--draft-pr` is passed and the user explicitly confirms after the hand-back artefact, following the adversarial review in [pre-pr-adversarial-review.md](pre-pr-adversarial-review.md).

The skill:

1. Shows the user the proposed PR title, body, and diff (one
   final review surface).
2. On explicit confirmation, opens a **draft** PR from the user's
   fork against `<upstream>:<default-branch>` with
   `gh pr create --web --draft`, pre-filling `--title` and `--body`
   (including the generative-AI disclosure block) so the human
   reviews the title, body, and disclosure in the browser before
   submitting — per
   [`AGENTS.md` → *"Always open PRs with `gh pr create --web`"*](../../../../AGENTS.md#commit-and-pr-conventions).
   Never non-draft; never on autopilot; never submitted without the
   browser step.
3. Does NOT post to `<issue-tracker>`, does NOT self-assign, does
   NOT transition workflow state. Those remain the maintainer's
   actions.

Without `--draft-pr`, this step is skipped entirely. The
hand-back artefact is the terminal output.
