<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `too-large` — over the footprint budget

Gate-green, but `additions + deletions` exceeds `max_churn` (default 20) or the files exceed `max_files` (default 3).
Pure deletions count: deleting forty lines is not trivial just because it adds nothing.
A "so-close" PR, reported with its number — it belongs to `pr-management-code-review` ([`actions/hand-off.md`](../actions/hand-off.md)).
[`quick-merge screen`](../../../../../tools/pr-management/README.md#quick-merge-screen--pr-management-quick-merge) measured it.
