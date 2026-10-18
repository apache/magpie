<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Skip — the viewer authored the PR

GitHub refuses a review from a PR's own author, so [`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) auto-skips it: *"PR #N is authored by `<viewer>`. GitHub doesn't allow self-review. Skipping."* The `guard` command checks it again right before posting.
