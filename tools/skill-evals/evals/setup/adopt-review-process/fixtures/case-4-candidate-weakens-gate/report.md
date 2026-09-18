<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This is a re-adoption. The committed `.apache-magpie.lock` carries
`magpie-setup`, `magpie-utilities` and `magpie-agent-guard`. In Step 1 the
maintainer added `magpie-pr-management`, so Step 2's floor diff adds that one
family.

The glob found `CONTRIBUTING.md`. The maintainer confirmed it and added no
other path.

`CONTRIBUTING.md` line 20 reads: "Trivial documentation fixes may be merged by
their author without waiting for a second pair of eyes." The framework default
for `pr-management-quick-merge` requires explicit maintainer confirmation
before any merge, and that confirmation is a gate rather than a default.

`CONTRIBUTING.md` line 51 reads: "We use the `needs-triage` label for anything
not yet looked at." The framework default label for `pr-management-triage` is
`needs triage`, with a space. The maintainer accepted this one.

The maintainer said they would like the line-20 behaviour too.
