<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Ready to merge

Every gate is green, the PR is trivial, and the live read says the branch merges now: `clean` / `has_hooks`, or `unstable` (a *non-required* check is not green — every required one already proved green) or `behind` (stale but clean; GitHub fast-forwards).
The entry carries the exact `merge_command`. The skill never runs it: the maintainer reads the diff and runs it in their own session.
