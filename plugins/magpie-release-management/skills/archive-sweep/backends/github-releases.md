<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Archive backend — `github-releases`

**Listing.** `gh release list --repo <upstream> --exclude-drafts` — each published (non-draft) release tag is a candidate.

**Archive.** One `gh release delete <ver> --repo <upstream> --yes` per past-retention version, oldest first.

`gh release delete` removes the release page and optionally the tag.
Include a reminder that GitHub releases have no archive equivalent; deletion is permanent.
The RM should confirm this is intentional.
`render` returns that reminder as `deletion_warning`: show it with the commands.
