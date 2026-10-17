<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Approval signal — `pr-approval`

Fetch the approvals from the release PR matching `approval_pr_branch_pattern`:

```bash
gh pr list --repo <upstream> \
  --head <approval_pr_branch_pattern> \
  --state open \
  --json number,reviews \
  --limit 1
```

Save that output and hand it to the tally as it is; never count the reviews yourself:

```bash
uv run --project <framework>/tools/release-management release-management vote-tally tally \
  --pr-reviews <scratch>/pr-reviews.json --login-map <scratch>/login-map.json \
  --roster <scratch>/roster.md --mechanism pr-approval --min-approvals <approval_pr_min_approvals>
```

Each reviewer's **latest** review (by `submittedAt`) is their vote; `COMMENTED` and pending reviews are not decisions and are skipped.
`APPROVED` is `+1`, `CHANGES_REQUESTED` is `-1`, and `DISMISSED` withdraws the vote, so an approval followed by a change request or a dismissal is never a `+1`.
The rule counts approvals only: a `-1` is reported in `binding_minus1` and in the `[RESULT]`, and its effect on the result is that the reviewer's `+1` is gone.
`pr_reviewers` in the output lists what decided each reviewer's vote.
A bare GitHub login never matches the roster, so `--login-map` (a JSON object, login to roster `Primary email`, from the mapping the RM provides) maps each one before tallying; an unmapped login is non-binding.

**The pass rule is code:** pass `approval_pr_min_approvals` to the tally as `--min-approvals <N>`.
`result` is `PASSED` when the binding approvals reach `N`, and `pass_rule_applied` names the rule.
Without the key the rule is unknown and `result` is `null`: block and ask the RM to set it.
Not available to an ASF project (Golden rule 6).
