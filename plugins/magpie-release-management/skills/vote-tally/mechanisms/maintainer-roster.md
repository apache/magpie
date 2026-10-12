<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Approval signal — `maintainer-roster`

Read the signed-approval file at the path configured in `release-management-config.md`.
It is an off-band signal the RM records by hand; each signed approval is a `+1` from that maintainer, and only roster members bind.

**The pass rule is not specified** for this mechanism, so it stays with you:
`vote-tally tally --mechanism maintainer-roster` returns `result: null`.
Verify the count and roster membership against the rule `release-management-config.md` declares, and pass the outcome to the Step 3 render as `--result PASSED|FAILED --rule "<the rule applied>"`.
Not available to an ASF project (Golden rule 6).
