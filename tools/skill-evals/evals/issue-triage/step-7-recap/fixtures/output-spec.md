<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "distribution": {
    "BUG": <count>,
    "FEATURE-REQUEST": <count>,
    "NEEDS-INFO": <count>,
    "DUPLICATE": <count>,
    "INVALID": <count>,
    "ALREADY-FIXED": <count>
  },
  "posted": [
    {"key": "<KEY>", "class": "<CLASS>", "comment_url": "<URL>"}
  ],
  "next_step_skills": {
    "issue-fix-workflow": ["<KEY>", ...],
    "closure-flow": ["<KEY>", ...]
  }
}
```

`issue-fix-workflow` contains keys classified BUG or FEATURE-REQUEST.
`closure-flow` contains keys classified INVALID, DUPLICATE, or ALREADY-FIXED.
NEEDS-INFO keys appear in neither list (awaiting reporter response).
Route strictly by classification: every posted key lands in `issue-fix-workflow`,
in `closure-flow`, or (for NEEDS-INFO only) in neither, never in both.
List the keys in `posted`, `issue-fix-workflow`, and `closure-flow` in the same
order they appear in the input, and copy each `comment_url` exactly as given.
`distribution` counts every posted item once, so its six counts sum to the
length of `posted`.
Do not include any text outside the JSON object.
