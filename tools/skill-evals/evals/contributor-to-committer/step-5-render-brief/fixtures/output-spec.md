<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "traffic_light_symbol": "✓ Ready to nominate | ~ Approaching | ✗ Not yet",
  "gap_table_correct": true | false,
  "timeline_present": true | false,
  "summary_paragraph_present": true | false,
  "offers_save_to_file": true | false,
  "offers_handoff_to_nomination": true | false,
  "no_github_mutation": true | false
}
```

- `traffic_light_symbol`: must be exactly one of the three specified strings
- `gap_table_correct`: true if the gap column shows "−N" for APPROACHING/NOT_YET dimensions and "—" for MET dimensions
- `timeline_present`: true if an activity timeline bar chart is included
- `summary_paragraph_present`: true if a one-paragraph summary is present naming the traffic-light colour and (for non-Ready) the specific gaps
- `offers_save_to_file`: true if the brief offers to save to a file
- `offers_handoff_to_nomination`: true if the brief offers to hand off to contributor-nomination
- `no_github_mutation`: true if the skill produces no GitHub mutations (read-only)

Do not include any text outside the JSON object.
