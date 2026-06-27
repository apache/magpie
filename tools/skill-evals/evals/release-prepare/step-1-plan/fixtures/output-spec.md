<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 1 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "issue_title": "<string>",
  "issue_body": "<string>",
  "pr_set_size": <integer>,
  "previous_tag": "<tag string>",
  "empty_pr_set": false,
  "proposed": true
}
```

OR, when the PR set is empty and --skip-empty-check was NOT passed:

```json
{
  "empty_pr_set": true,
  "previous_tag": "<tag string>",
  "handoff_reason": "<string>"
}
```

Grading rules:
- `proposed` must always be `true` in the non-empty-set path.
- `empty_pr_set` must be `true` and `handoff_reason` non-empty when
  no PRs were merged since the previous tag and --skip-empty-check
  was not passed.
- `issue_title` must contain the version string.
- `pr_set_size` must equal the count of PRs described in the report.
- No extra keys are permitted in the non-empty-set response.
