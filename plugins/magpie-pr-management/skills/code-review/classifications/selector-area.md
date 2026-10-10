<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Selector `area:<LBL>` — filter by area label

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) keeps PRs carrying the label. Literal labels (`area:scheduler`) and prefix wildcards (`area:provider*`, `provider:amazon` — some projects use `provider:` instead of `area:`) both work; the wildcard is matched after the fetch, since GitHub search does not expand label wildcards.

It filters the union, not each signal: `area:scheduler` drops any PR — review-requested or touching-mine — without that label. To keep only review-requested PRs in the area, add `requested-only`. Combine with `ready` for the area filter without the my-reviews signals.
