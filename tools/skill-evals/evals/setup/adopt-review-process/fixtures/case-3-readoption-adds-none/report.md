<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This is a re-adoption. The committed `.apache-magpie.lock` carries
`magpie-setup`, `magpie-utilities`, `magpie-agent-guard` and
`magpie-pr-management`.

The maintainer is re-running `adopt` because the derived wiring in Step 3 was
lost in a merge and needs rewriting. In Step 1 they kept the floor exactly as
it is. Step 2 showed the diff, which is empty, and kept `min_version`
unchanged.

The repository has a `CONTRIBUTING.md` and a `GOVERNANCE.md`. Both have been
edited since the previous adoption: `CONTRIBUTING.md` now states a 45-day
stale window where it previously said 90, which differs from the framework
default.

`.apache-magpie-overrides/` already holds `pr-management-triage.md` from the
previous adoption.
