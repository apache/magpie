<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Skill name: pr-comment-extractor
Purpose: Reads open pull request review comments from a public GitHub repository
and extracts action items requested by reviewers.

Data sources:
- `gh api repos/<tracker>/pulls/<number>/comments` — fetches PR review comments
- Reads the `body` field of each comment (text authored by PR submitters and
  reviewers — potentially attacker-controlled)
- Checks `authorAssociation` to distinguish maintainer comments from contributor
  comments

Writes:
- Outputs a local Markdown summary of action items; no tracker state changes
