<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "chosen_block": {
    "location": "body | comment-<N> | attachment-<filename>",
    "language": "<canonical lower-case language name, e.g. python | javascript | java | bash | sql | yaml> | unknown",
    "line_count": <integer>
  },
  "reason": "<brief phrase: 'only block' | 'simplest complete' | 'maintainer-simplified' | 'explicit entry point stated'>",
  "fallback_chain": [
    {"location": "<location>", "reason": "<why it's the fallback>"}
  ]
}
```

`fallback_chain` is empty when there is only one block.
Do not include any text outside the JSON object.
