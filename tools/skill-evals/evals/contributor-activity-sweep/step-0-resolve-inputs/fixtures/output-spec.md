## Output format

Return ONLY valid JSON with this structure:

```json
{
  "login_accepted": true | false,
  "rejection_reason": "<one sentence or null>",
  "since": "<ISO-8601 date the window starts, or null if login rejected>",
  "window_trimmed": true | false,
  "trim_reason": "<one sentence or null>"
}
```

- `login_accepted`: false when the handle fails the regex validation check
- `rejection_reason`: one sentence explaining rejection, or null when accepted
- `since`: the resolved start date of the window (after any repo-age trim), or null if rejected
- `window_trimmed`: true when the repo creation date is newer than the computed `<since>`
- `trim_reason`: one sentence explaining the trim, or null when not trimmed

Do not include any text outside the JSON object.
