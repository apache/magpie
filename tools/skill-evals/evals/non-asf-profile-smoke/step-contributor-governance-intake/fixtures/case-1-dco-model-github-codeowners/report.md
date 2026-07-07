<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

candidate_info:
  Name: Sam Rivera
  Email: srivera@example.com
  Desired GitHub handle: srivera-dev
  Existing GitHub handle: srivera-dev
  Project: Velox Stream (non-ASF, github-codeowners governance)
  Scenario: new-committer
  Nominator: @alex-velox
  Vote thread: https://github.com/velox-community/velox-stream/discussions/1042

committer-onboarding-config.md:
  committer_intake.model: dco
  committer_intake_dco.reference_url: https://developercertificate.org/
  committer_intake_dco.min_signed_off_prs: 1
  committer_governance.model: github-codeowners
  committer_governance_github_codeowners.maintainers_team: velox-community/velox-stream-maintainers
  committer_governance_github_codeowners.codeowners_file: CODEOWNERS
  committer_governance_github_codeowners.vote_channel: github-discussion

dco_check:
  Searched srivera-dev's last 5 merged PRs in velox-community/velox-stream
  PRs with Signed-off-by: 3 of 5
  min_signed_off_prs: 1
  Result: DCO check PASSED (3 >= 1)

No ICLA infrastructure exists for this project (non-ASF). Whimsy lookup not applicable.
No ASF secretary account-request step.
