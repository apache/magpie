<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Step 3 — Session summary

Each PR's outcome is recorded with `uv run --project <framework>/tools/pr-management pr-management code-review session record` as the loop goes
(Step 9 of [`review-flow.md`](review-flow.md)). On exit, print the `text` of
`uv run --project <framework>/tools/pr-management pr-management code-review session summary --session <scratch>/cr-session.json --untouched <count>`:
reviews per disposition, skips with the maintainer's reasons, PRs left
untouched, which PRs had adversarial findings folded in, time, throughput and
the GitHub calls spent. The summary is for the maintainer's records — this
skill never writes a session log anywhere else.
