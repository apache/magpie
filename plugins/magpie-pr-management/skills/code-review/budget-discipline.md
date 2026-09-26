<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Budget discipline

This skill's practical GraphQL / `gh` budget per PR is:

- 1 query for the working PR list (one-shot, at session start)
- 1 `gh pr view --json body,reviewRequests,reviews,statusCheckRollup,commits,labels,...` per PR
- 1 `gh pr diff` per PR
- 0–1 calls into the adversarial reviewer (out-of-band, not
  GitHub API)
- 0–1 `CODEOWNERS` read + 0–3 `commits?path=` reads for the
  Step 4.5 reviewer suggestions (the PR-review-history source is
  reached only when the cheap sources fall short)
- 1 `gh pr review` mutation per posted review

That's ~3 GitHub calls per PR plus one optional plugin call.
A normal review pass (5–10 PRs) stays well under 100 GitHub-API
points — a tiny fraction of the maintainer's 5000/h budget. If a
session starts approaching the limit, the skill is
mis-batching (most likely: re-fetching the diff after every
finding instead of caching it locally) — stop and fix the call
pattern, do not work around it with rate-limit sleeps.
