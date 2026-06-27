## Output format

Return ONLY valid JSON with this structure:

```json
{
  "verdict": "proceed" | "blocked",
  "blockers": ["<string describing each hard blocker>"],
  "kept": <integer>,
  "duplicate": <integer>
}
```

- `verdict` is `"proceed"` only when all hard blockers resolve.
- `blockers` lists each unresolved hard blocker as a human-readable string.
- `kept` is the issue number that will remain open.
- `duplicate` is the issue number that will be closed.
- When only one issue number was supplied, `verdict` must be `"blocked"` and
  `blockers` must name the missing second argument.
- When either issue is already closed or already labelled `duplicate`,
  `verdict` must be `"blocked"`.

Do not include any text outside the JSON object.
