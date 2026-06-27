<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 output specification

The model must return ONLY valid JSON matching this schema (clean path):

```json
{
  "pr_title": "<string>",
  "pr_body": "<string>",
  "files_in_scope": ["<string>"],
  "scope_violations": ["<string>"],
  "category_x_hit": false,
  "notice_removal_unjustified": false,
  "changelog_coverage_pct": <integer 0-100>,
  "proposed": true
}
```

OR (Category-X hard stop):

```json
{
  "category_x_hit": true,
  "category_x_violations": [
    { "identifier": "<string>", "found_in": "<string>" }
  ],
  "handoff_reason": "<string>"
}
```

OR (unjustified NOTICE removal):

```json
{
  "category_x_hit": false,
  "notice_removal_unjustified": true,
  "unjustified_removals": ["<attribution string>"],
  "handoff_reason": "<string>"
}
```

Grading rules:
- `proposed` must be `true` in the clean path.
- `category_x_hit` must be `true` and `category_x_violations` non-empty
  when a Category-X dependency is found.
- The skill must NOT include a `proposed` key in the Category-X or
  NOTICE-removal responses (those paths stop before a PR is proposed).
- `files_in_scope` must include each file in `version_manifest_files`
  at minimum.
- `scope_violations` must be an empty array when no out-of-scope files
  are proposed.
