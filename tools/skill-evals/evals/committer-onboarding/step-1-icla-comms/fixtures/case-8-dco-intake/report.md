<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

candidate_info:
  Name: Priya Sharma
  Email: priya@example.com
  GitHub handle: psharma-oss
  Existing account: none (no prior committer role)
  Project: ExampleProject (non-ASF, github-codeowners governance)
  Scenario: new-committer
  Nominator: jmclean

intake_config:
  committer_intake:
    model: dco
  committer_intake_dco:
    reference_url: https://developercertificate.org/
    min_signed_off_prs: 2

dco_check:
  prs_checked: 3
  prs_with_signed_off: 2
  prs_without_signed_off: 1
  result: PASS (2 of 3 checked PRs carry Signed-off-by; meets min_signed_off_prs=2)
