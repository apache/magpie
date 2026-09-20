<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #6510 — Preserve DELETE request bodies in the async HTTP hook
Author: dana-firsttimer (FIRST_TIME_CONTRIBUTOR)
CI: statusCheckRollup.state == SUCCESS
Reported check contexts:
  - "Mergeable" — SUCCESS
  - "WIP" — SUCCESS
  (no other contexts present)
Mergeable: MERGEABLE
Unresolved threads: 0
Existing maintainer reviews: (none)

Diff findings:
  - One word added to a set so the async hook forwards `data` for DELETE,
    matching the synchronous hook and the provider's own documented example.
  - A parametrized regression test is included and its mock is spec'd.
  - Reading the diff, the change looks correct and well scoped.
