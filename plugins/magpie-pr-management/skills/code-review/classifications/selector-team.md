<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Selector `team:<NAME>` — team review requests

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) keeps open PRs where review is requested from team `<NAME>` (the team must be one the viewer belongs to for the queue to be theirs to work).
Useful for committers on several team queues (e.g. `<upstream>-providers-amazon`). The match is on the PR's requested teams in the saved sweep; no extra search runs.
