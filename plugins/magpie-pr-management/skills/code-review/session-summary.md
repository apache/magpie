<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Step 3 — Session summary

On exit (whether by `[Q]uit` or by exhausting the working list),
print a one-screen summary:

- counts of PRs reviewed per disposition (`APPROVE` /
  `REQUEST_CHANGES` / `COMMENT`)
- counts of PRs skipped, with the maintainer's stated reason
  (e.g. "wanted to re-look later", "needs author response first")
- counts of PRs left untouched (selector match but never reached
  this session)
- which PRs had adversarial-reviewer findings folded in, and
  which didn't (because the maintainer skipped that step)
- total wall-clock time and PRs-per-hour velocity

The summary is for the maintainer's records — this skill never
writes a session log to disk.
