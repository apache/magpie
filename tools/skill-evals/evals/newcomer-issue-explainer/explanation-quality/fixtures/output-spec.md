## Output format

Return ONLY valid JSON with this structure:

```json
{
  "passed": true | false,
  "failing_checks": ["<check-code>", ...]
}
```

- `passed` is `true` when `failing_checks` is `[]`.
- `failing_checks` lists every failing check code (E1–E5), sorted
  alphabetically.
- Do not include any text outside the JSON object.
