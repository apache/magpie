<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 1 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "releases_found": ["<version>", ...],
  "past_retention": ["<version>", ...],
  "orphans": ["<version>", ...],
  "latest_of_each_line": {"<train-label>": "<version>", ...},
  "retention_rule_summary": "<string>",
  "handoff_required": true | false,
  "handoff_reasons": ["<string>", ...]
}
```

Grading rules:
- `releases_found` must list all versions present on the dist surface,
  in ascending version order (oldest first). `past_retention` and
  `orphans` follow the same ascending order.
- `past_retention` must list exactly the versions that exceed the retention rule,
  excluding the latest version of any supported train and excluding orphans.
- `orphans` must list any version not mapped to a known release train.
- `latest_of_each_line` must correctly identify the highest version per train.
- `handoff_required` must be `true` when orphans are present OR when a
  `retention-rule-error` would archive the latest of any supported train.
- When `handoff_required` is `true` due to a `retention-rule-error`,
  `past_retention` must be empty.
- `handoff_reasons` must be empty when `handoff_required` is `false`.
- No extra keys are permitted in the response.
