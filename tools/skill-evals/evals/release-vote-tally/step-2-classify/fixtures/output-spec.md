<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "classifications": [
    {
      "from": "<email or GitHub handle>",
      "date": "<ISO-8601>",
      "binding": true | false,
      "value": "+1" | "0" | "-1" | "fractional",
      "ambiguous": false,
      "raw_vote_line": "<verbatim vote line>"
    }
  ],
  "ambiguous": [
    {
      "from": "<email or GitHub handle>",
      "date": "<ISO-8601>",
      "raw_vote_line": "<verbatim vote line>",
      "reason": "<why it is AMBIGUOUS>"
    }
  ]
}
```

Grading rules:
- Each non-ambiguous reply appears in `classifications` exactly once.
- Replies from roster members resolve to `binding: true` via exact email match
  or Apache-ID-to-local-part match.
- Replies with no roster match resolve to `binding: false`.
- Fractional votes (`+0.5`, `+0.9`, etc.) appear in `classifications` with
  `value: "fractional"` and `binding: false`, never in `ambiguous`.
- Conditional, unclear, or retracted replies appear in `ambiguous` only and
  never in `classifications`.
- `ambiguous` is an empty array when no ambiguous votes are present.
- No extra keys are permitted.
