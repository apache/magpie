<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Selector `pr:<N>` — one PR

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `queue pr:<N>` puts exactly that PR on the list. It bypasses every other filter — `collab:`, drafts, the five signals: the maintainer asked for this PR, the skill reviews it.
Read the PR with `gql-cr-pr <N>`; a draft or a "WIP" / "do not merge" title still asks before the review starts ([`skip-draft.md`](skip-draft.md), [`skip-wip-title.md`](skip-wip-title.md)).
