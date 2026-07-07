<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "recap_text": "<the full recap, verbatim markdown>",
  "request_update_count": <integer>,
  "close_stale_count": <integer>,
  "closed_count": <integer>,
  "skipped_count": <integer>,
  "security_flagged_count": <integer>,
  "maintainer_court_count": <integer>
}
```

`recap_text` is the exact recap you would show the user. Emit the real text,
not a description of it. The grader inspects this text directly, so it must:

- include a note that security-flagged PRs were skipped and still need manual review, whenever any security-flagged PRs are present,
- include a reminder that maintainer-court PRs (author awaiting a maintainer response) still need a maintainer to respond, whenever any are present,
- reference EVERY PR as a clickable link (markdown `[#NNN](url)` or an OSC 8 terminal hyperlink), never a bare `#NNN`. This is mandatory for all PR numbers, including ones that only need a passing mention. For example, write `[#42](https://github.com/apache/myproject/pull/42)`, not `#42`. Before returning, scan `recap_text` and confirm that no `#NNN` token appears outside a `[...]( ... )` link or OSC 8 escape.

The `*_count` fields are the exact tallies for the sweep and are compared
directly.

Do not include any text outside the JSON object.
