## Output format

Return ONLY valid JSON with this structure:

```json
{
  "test_has_issue_key": true | false,
  "adapts_from_reproducer": true | false,
  "confirmed_failing": true | false,
  "verdict": "accept | reject | surface-gap"
}
```

`test_has_issue_key` is true when the issue key appears in the test name or a docstring/comment.
`adapts_from_reproducer` is true when a reproducer verdict was supplied and the test is based on it; false when no reproducer was provided (acceptable) or when a reproducer was provided but the test ignores it (not acceptable).
`confirmed_failing` is true when the test run output shows the test fails on the default branch as expected.
`verdict` is `accept` when all properties hold; `surface-gap` when the test passes on main (silent-broken-test trap); `reject` when any required property is missing or malformed.
Do not include any text outside the JSON object.
