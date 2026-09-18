<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This is a re-adoption. The committed `.apache-magpie.lock` already carries
`magpie-setup`, `magpie-utilities`, `magpie-agent-guard` and
`magpie-pr-management`. In Step 1 the maintainer added `magpie-issue`, so
Step 2's floor diff adds exactly that one family and changes nothing else.

The glob found `CONTRIBUTING.md` and `GOVERNANCE.md`. The maintainer confirmed
both.

`CONTRIBUTING.md` line 42 still reads "Every pull request needs approvals from
two committers before it may be merged." An override for
`pr-management-triage` recording that was written during the previous
adoption and is committed.

`GOVERNANCE.md` line 15 reads: "Issues that go 14 days without a reply from
the reporter are closed as inactive." The framework default for
`issue-stale-sweep` is 60 days. The maintainer accepted this one.

`GOVERNANCE.md` line 60 describes the PMC's voting procedure for new
committers. The contributor-growth family is not in the floor.
