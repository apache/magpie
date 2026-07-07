<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "comment_body": "<the full composed comment, verbatim markdown>",
  "class": "REQUEST-UPDATE | CLOSE-STALE"
}
```

`comment_body` is the exact comment you would post on the PR, including any
HTML-comment markers and PR references. Emit the real text, not a description
of it. The grader inspects this text directly, so it must contain:

- the literal HTML comment `<!-- pr-stale-sweep-nudge -->`,
- PR references as markdown links (e.g. `[#42](https://github.com/apache/myproject/pull/42)`), never a bare `#NNN`,
- for a REQUEST-UPDATE comment, the approximate number of days remaining before the PR is closed.

`class` is the classification the comment is written for.

Do not include any text outside the JSON object.
