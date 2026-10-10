<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `wrong-layer`

[`stack-review findings`](../../../../../tools/pr-management/README.md) lists candidates: files more than one layer changes, and off-theme files of a layer.
Read the commit bodies first: a placement a commit or the PR body explains is placed on purpose — at most a `minor` narrative *body omits what the commit says*, never wrong-layer.

When the hunk's content belongs to another layer's stated purpose, record it with `layers` = the carrying layer and the owning layer:

- `minor` as an unread candidate, and for mechanical spillover that leaves the end state unchanged;
- `major` only when it changes a layer's green-on-its-own status, its packaging or its runtime behaviour.
