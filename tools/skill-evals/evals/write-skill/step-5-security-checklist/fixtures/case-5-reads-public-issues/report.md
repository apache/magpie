<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Skill name: issue-labeller
Purpose: Reads open GitHub issues from a public tracker and proposes labels
based on their title and body.

Data sources:
- `gh issue list --repo <tracker>` — fetches open issues
- Reads `title` and `body` of each issue (user-submitted, externally controlled)
- Reads issue comments to check for maintainer context

Writes:
- Proposes label additions via `gh issue edit --add-label` after user confirmation
