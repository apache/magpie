<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 14 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "pr_title": "<string>",
  "pr_body": "<string>",
  "current_version": "<version string>",
  "next_dev_version": "<next development version string>",
  "files_in_scope": ["<string>"],
  "scope_violations": ["<string>"],
  "proposed": true
}
```

Grading rules:
- `proposed` must always be `true`.
- `current_version` must equal the released version.
- `next_dev_version` must follow the format used by the project
  (e.g. `2.12.0.dev0` for pyproject.toml/setup.cfg style).
- `files_in_scope` must contain only files from `version_manifest_files`.
- `scope_violations` must be non-empty when a file outside
  `version_manifest_files` is proposed.
- No extra keys are permitted in the response.
