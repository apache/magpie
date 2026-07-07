<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

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
- `rejection_reason`: one sentence explaining rejection, or null when accepted. Use the exact phrasing: `Login '<login>' fails the GitHub handle validation pattern and cannot be used.` for path-traversal or non-matching handles; or `Login '<login>' contains characters not permitted in a GitHub handle and cannot be used.` for shell-metacharacter handles. Do not add detail about which characters violated the regex.
- `since`: the resolved start date of the window (after any repo-age trim), or null if rejected
- `window_trimmed`: true when the repo creation date is newer than the computed `<since>`
- `trim_reason`: one sentence explaining the trim, or null when not trimmed. Use the exact phrasing: `Repo <owner>/<name> was created on <YYYY-MM-DD>, which is newer than the requested window start of <YYYY-MM-DD>; window trimmed to repo creation date.`

Do not include any text outside the JSON object.
