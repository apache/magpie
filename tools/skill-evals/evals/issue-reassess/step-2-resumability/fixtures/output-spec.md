<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "campaign_id": "<campaign id in use>",
  "candidates": [
    {"key": "<KEY>", "state": "reuse" | "ask-refresh-or-reuse" | "resume" | "fresh"}
  ]
}
```

`state` per candidate, from the table above:

- `reuse` — `verdict.json` exists and its `rev` matches the current
  `<default-branch>` rev; skip and reuse it.
- `ask-refresh-or-reuse` — `verdict.json` exists but was produced against
  a different rev; the user decides.
- `resume` — partial artefacts exist (a `description.md` was written, no
  `verdict.json`); pick up where it stopped.
- `fresh` — no artefacts for this candidate.

`campaign_id` is the id the user supplied, else the auto-generated
`reassess-<date>` form using the date given in the input.
List `candidates` in the order they were given.
Do not include any text outside the JSON object.
