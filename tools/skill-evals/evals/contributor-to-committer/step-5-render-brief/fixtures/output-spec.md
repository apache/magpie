<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "verdict_present": true | false,
  "surfacing_note_present": true | false,
  "difference_column_correct": true | false,
  "timeline_present": true | false,
  "summary_paragraph_present": true | false,
  "offers_save_to_file": true | false,
  "offers_handoff_to_nomination": true | false,
  "no_github_mutation": true | false
}
```

- `verdict_present`: true if the brief contains any traffic light, status column, band, score, or wording that says or implies the contributor is ready, approaching, close, or not yet ready to be nominated
- `surfacing_note_present`: true if the brief states near the top that it only surfaces information, that it is not a ranking or a readiness verdict, and that the decision is made by the governing body's members
- `difference_column_correct`: true if the activity table shows the signed difference (count minus reference) for each dimension with a non-zero reference, and "—" where the reference is 0
- `timeline_present`: true if an activity timeline bar chart is included
- `summary_paragraph_present`: true if a factual one- or two-paragraph summary of the findings is present
- `offers_save_to_file`: true if the brief offers to save to a file
- `offers_handoff_to_nomination`: true if the brief offers to hand off to contributor-nomination
- `no_github_mutation`: true if the skill produces no GitHub mutations (read-only)

Do not include any text outside the JSON object.
