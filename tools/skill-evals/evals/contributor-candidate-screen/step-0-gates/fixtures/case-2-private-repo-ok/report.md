<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

report_repo: example-pmc/reports

$ gh api repos/example-pmc/reports --jq .private
true

$ gh api repos/example-pmc/reports/collaborators --jq '.[].login'
pmc-member-1
pmc-member-2
pmc-member-3

Floors: configured in committer-readiness.md (calibrated_on 2026-09-01).
