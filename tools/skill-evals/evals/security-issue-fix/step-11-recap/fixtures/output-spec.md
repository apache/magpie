<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — Step 11 recap

Return a JSON object with these boolean fields asserting the structural properties of the recap.

```json
{
  "has_pr_url": <bool — recap includes the full public PR URL>,
  "has_branch_name": <bool — recap names the branch in the user's fork>,
  "has_files_changed": <bool — recap lists the files that were modified>,
  "has_test_results": <bool — recap reports the outcome of the local test and check commands>,
  "has_tracker_comment_ref": <bool — recap references the comment posted on the tracker issue>,
  "has_backport_label": <bool — recap mentions the backport label applied (or explicitly states none was needed)>,
  "has_next_step": <bool — recap ends with a next-step sentence (e.g. wait for review, re-run security-issue-sync after merge)>,
  "has_bare_issue_numbers": <bool — recap contains a bare #NNN reference without a full URL — should be false>
}
```

Every field above MUST always be present in the returned object; never omit
a field. In particular, `has_next_step` MUST always be present and is `true`
whenever the recap ends with the next-step line (wait for review; re-run
security-issue-sync after the PR merges).
