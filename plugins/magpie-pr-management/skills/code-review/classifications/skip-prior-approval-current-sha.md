<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Skip — already approved at the current head

The viewer's latest `APPROVED` review was submitted against the PR's current head SHA: there is nothing new to read, and re-approving adds noise to the review history.
[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) auto-skips it: *"PR #N already has an APPROVED review from `<viewer>` against the current head. Skipping — re-approval is redundant."* Record it as a `prior-approval` skip in the session summary.
