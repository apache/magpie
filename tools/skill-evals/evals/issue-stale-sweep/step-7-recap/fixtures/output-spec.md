<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "request_update_count": <integer>,
  "close_stale_count": <integer>,
  "closed_count": <integer>,
  "skipped_count": <integer>,
  "security_flagged_count": <integer>,
  "has_security_routing_note": true | false,
  "has_bare_issue_ref": true | false
}
```

`has_security_routing_note` is true when the recap text includes a
reminder to route security-flagged issues privately.
`has_bare_issue_ref` is true when the recap text contains a bare `#NNN`
reference not inside a markdown link or OSC 8 wrapper.
Do not include any text outside the JSON object.
