<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Approval signal — `github-discussion`

Fetch the approval discussion from `<upstream>` using `approval_discussion_repo` and `approval_discussion_category`:

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      discussion(number: $number) {
        comments(first: 100) {
          nodes { body author { login } createdAt }
        }
      }
    }
  }' -F owner=<owner> -F repo=<repo> -F number=<discussion-number> \
  --jq '.data.repository.discussion.comments.nodes[]'
```

Extract the vote value from each reply body as for a list vote (Step 1).
A bare GitHub login never matches the roster, so map each login to its roster `Primary email` with the mapping the RM provides before tallying; an unmapped login is non-binding.

**The pass rule is not specified** for this mechanism, so it stays with you:
`vote-tally tally --mechanism github-discussion` returns `result: null`.
Apply the rule `release-management-config.md` declares to the tally's counts, and pass the outcome to the Step 3 render as `--result PASSED|FAILED --rule "<the rule applied>"`.
Not available to an ASF project (Golden rule 6).
