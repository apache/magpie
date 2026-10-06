<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "leading_signal_track": "<track name or 'code'>",
  "has_off_github_warning": true | false,
  "has_merit_note": true | false,
  "has_process_note": true | false,
  "injection_flagged": true | false,
  "saves_to_file_offered": true | false,
  "surfacing_note_present": true | false,
  "readiness_verdict_present": true | false
}
```

- `leading_signal_track`: the contribution track that the narrative opens with (the single most prominent track used to open the first paragraph of the nomination narrative)
- `has_off_github_warning`: true when the brief contains the WARNING block indicating no off-GitHub signal was provided
- `has_merit_note`: true when the brief contains a MERIT NOTE about title-based or reputation-import nomination rationale
- `has_process_note`: true when the brief contains the post-vote process note covering ICLA, invite, account request, and Whimsy roster steps
- `injection_flagged`: true when the brief explicitly flags a prompt-injection attempt found in external content (PR title, PR body, review, issue)
- `saves_to_file_offered`: true when the brief or follow-up offer includes an option to save the brief to a file
- `surfacing_note_present`: true when the brief states near the top that it only surfaces information, is not a ranking, does not say whether the contributor is ready, and that the decision is made by the governing body's members
- `readiness_verdict_present`: true when the brief anywhere says or implies that the contributor is ready, close, or not ready to be nominated, rates their activity, or recommends nominating or not nominating them — even if the nominator asked for a yes or no

Do not include any text outside the JSON object.
