<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR draft shown to user:

Title: feat(skills): add draft-PR short-circuit gate to pr-management-triage

Body:
## Summary
- Add a draft-state check at the start of `pr-management-triage` Step 1.
- When a PR is in GitHub draft state, skip triage and post a comment asking
  the author to re-invoke once the PR is ready for review.
- Controlled by a `skip_draft_prs` config key (default: `true`).

## Motivation
Apache Airflow's adopter override `.apache-magpie-overrides/pr-management-triage.md`
implements this behaviour locally ([link to override in adopter repo]).
Triage on draft PRs generates noise: labels are applied and routing happens
before the PR is ready, requiring manual cleanup when the PR is finalised.
Any adopter running a busy repository with many draft PRs would benefit.

## Migration path for existing adopters
The new `skip_draft_prs` config key defaults to `true`, so all adopters gain
the gate on upgrade. Adopters who prefer the old behaviour (triage on draft
PRs) can opt out by setting `skip_draft_prs: false` in their project config.

## Test plan
- [ ] Ran `skill-and-tool-validate` — passes.
- [ ] Manually tested against a draft PR in the adopter repo before opening this PR.
- [ ] Verified triage runs normally on non-draft PRs after the change.

User has not yet responded.
