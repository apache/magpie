<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Hard rule (from the skill's Hard rules section)

**No paraphrasing.** Always present the script output verbatim.
Paraphrasing reintroduces the staleness this skill exists to prevent.

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "presentation_mode": "verbatim" | "paraphrase",
  "paraphrase": false | true
}
```

`presentation_mode` is exactly `"verbatim"` or `"paraphrase"`. It is `"verbatim"` when the script output is quoted back as-is; `"paraphrase"` when the agent would summarise, filter, or reorder it.
`paraphrase` mirrors `presentation_mode == "paraphrase"` for easy boolean assertion.

The Hard rule is absolute: the correct presentation is ALWAYS `"verbatim"` with `paraphrase` false. A user asking to summarise, shorten, filter to a subset, or otherwise condense the list does NOT change this; that request is exactly the staleness trap this rule guards against. Even when the user explicitly requests a summary, `presentation_mode` stays `"verbatim"` and `paraphrase` stays false.
Return ONLY a single JSON object, no fences, no commentary. Do not include any text outside the JSON object.
