<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Selector `pr:<N>` — named PRs

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `queue pr:<N>` puts exactly that PR on the list; `pr:<N>,<M>`, `pr:<N>-<M>` (inclusive) and repeated `pr:` tokens put each named PR on it, in the order named (duplicates dropped, at most 50). It bypasses every other filter — `collab:`, drafts, the five signals: the maintainer asked for this PR, the skill reviews it.
A named PR that is not in the open-PR sweep (closed, merged, or a typo) is listed in the queue's `not_open`: say so and go on with the rest.
Read each PR with `gql-cr-pr <N>`; a draft or a "WIP" / "do not merge" title still asks before the review starts ([`skip-draft.md`](skip-draft.md), [`skip-wip-title.md`](skip-wip-title.md)).
