<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "fixes_cause": true | false,
  "in_scope": true | false,
  "targeted_test_green": true | false,
  "verdict": "proceed | iterate"
}
```

`fixes_cause` is true when the change addresses the root cause rather than adding a local symptom guard.
`in_scope` is true when the diff contains only the production change and any directly-required edits — no drive-by reformats, renames, or unrelated files.
`targeted_test_green` is true when the targeted regression test passes after the fix is applied.
`verdict` is `proceed` when all three properties hold; `iterate` otherwise.
Do not include any text outside the JSON object.
