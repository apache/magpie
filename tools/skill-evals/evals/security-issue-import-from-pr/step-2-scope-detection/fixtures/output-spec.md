<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **scope detection** step of the `security-issue-import-from-pr` skill.

A mock `gh pr view` response with the list of changed files is provided. Detect the scope and return the result.

Return a JSON object with exactly these fields:

```json
{
  "scope": "airflow" | "providers" | "chart" | "mixed_scope_blocker",
  "stop": true | false,
  "affected_providers": ["<name>"],
  "files_counted": ["<path>"],
  "test_files_stripped": ["<path>"],
  "rationale": "<one sentence>"
}
```

Field rules:
- `scope`: the detected scope, or `mixed_scope_blocker` if files span more than one scope.
- `stop`: `true` only for `mixed_scope_blocker` — a hard stop is required.
- `affected_providers`: list of provider names (e.g. `["amazon"]`) for `providers` scope; empty array otherwise.
- `files_counted`: the production file paths after test files are stripped (paths matching `*/tests/**` are excluded).
- `test_files_stripped`: test paths that were stripped before scope mapping (may be empty).
- `rationale`: one sentence.
