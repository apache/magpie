<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — Step 5a labels

Return an exact-match JSON object.

```json
{
  "labels_to_add": [<string> ...],
  "labels_to_remove": [<string> ...],
  "security_issue_stays": <bool — the `security issue` label is NOT removed>
}
```

Rules:
- `labels_to_add` must always contain `"invalid"` and nothing else.
- `labels_to_remove` contains all labels that must be stripped: `needs triage` (if present), the scope label (`airflow`, `providers`, or `chart`, if present), and `pr created` / `pr merged` (if present).
- `security_issue_stays` must always be `true` — the `security issue` label must never be removed.
- List entries in the order they appear in the SKILL.md spec (invalid → scope → pr labels).
