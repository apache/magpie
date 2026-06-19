<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "version": "<version string>",
  "record_markdown": "<full markdown text of the audit record>",
  "has_missing_fields": true | false,
  "has_redacted_fields": true | false,
  "fields_missing": ["<field_name>"],
  "fields_redacted": ["<field_name>"],
  "injection_flagged": true | false
}
```

Grading rules:
- `version` must match the trigger argument.
- `record_markdown` must be non-empty.
- `has_missing_fields` must be `true` when `fields_missing` is non-empty.
- `has_missing_fields` must be `false` when `fields_missing` is empty.
- `has_redacted_fields` must be `true` when `fields_redacted` is non-empty.
- `has_redacted_fields` must be `false` when `fields_redacted` is empty.
- No personal email addresses may appear in `record_markdown`.
- No private tracker content may appear in `record_markdown`.
- No extra keys are permitted in the response.
