<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "has_nudge_marker": true | false,
  "has_bare_issue_ref": true | false,
  "mentions_remaining_days": true | false,
  "class": "REQUEST-UPDATE | CLOSE-STALE"
}
```

`has_nudge_marker` is true when the composed comment body contains the
literal HTML comment `<!-- stale-sweep-nudge -->`.
`has_bare_issue_ref` is true when the comment body contains a bare `#NNN`
reference that is not inside a markdown link or OSC 8 wrapper.
`mentions_remaining_days` is true for REQUEST-UPDATE comments that include
the approximate days until closure.
Do not include any text outside the JSON object.
