<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Disposition `REQUEST_CHANGES`

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `disposition` picks it for at least one `blocking` finding, two or more `major`, one `major` with an unanswered author question (`--unanswered-question`), or a CI failure you judged diff-caused (`--ci-diff-caused`).
Summary line names the reason: *"Found 1 blocking issue (potential SQL injection in `where` clause) that needs to land before this can merge."*
On a backport base, prefer `COMMENT` unless the cherry-pick has clearly drifted ([`backport.md`](backport.md)).
