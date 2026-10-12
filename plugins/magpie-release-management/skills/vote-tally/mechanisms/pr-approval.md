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

Each `APPROVED` review is a `+1` from its author.
A bare GitHub login never matches the roster, so map each login to its roster `Primary email` with the mapping the RM provides before tallying; an unmapped login is non-binding.

**The pass rule is code:** pass `approval_pr_min_approvals` to the tally as `--min-approvals <N>`.
`result` is `PASSED` when the binding approvals reach `N`, and `pass_rule_applied` names the rule.
Without the key the rule is unknown and `result` is `null`: block and ask the RM to set it.
Not available to an ASF project (Golden rule 6).
